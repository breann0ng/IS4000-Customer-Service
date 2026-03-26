"""LangGraph workflow definition for the customer service chatbot.

Implements a plan-and-execute pattern where:
1. The planner analyzes the user query and creates an execution plan
2. The executor dispatches steps to specialist agents
3. A synthesizer combines all results into a final response

All LLM calls use Gemini with structured outputs via Pydantic models.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.escalation import check_escalation, escalation_node
from apps.api.workflow.executor import executor_node
from apps.api.workflow.planner import planner_node
from apps.api.workflow.state import SynthesizerOutput, WorkflowState

logger = get_logger(__name__)

SYNTHESIZER_SYSTEM_PROMPT = """You are a private wealth management assistant for UBS, serving High Net Worth Individual (HNWI) clients. You are given results from specialist agents who have analyzed the client's query.

Your job is to synthesize these results into a single, polished client-facing response.

---

## CRITICAL: Output Format Requirements

You MUST structure your response using Markdown with `###` section headers. Do NOT write a single paragraph or block of prose. Each section must be a separate `###` heading followed by its content.

### Required sections (use these exact headings):

### 1. Summary

A 2-3 sentence executive summary with key takeaways. Bold the most important numbers.

### 2. Current Portfolio Assessment

Reference the client's actual AUM, YTD performance, and allocation using exact figures from the specialist data. Bold metrics like **CHF 12.45M AUM** and **+6.8% YTD**.

### 3. Market Context

Bullet points covering relevant macro conditions, sector trends, and economic drivers.

### 4. Implications for Your Portfolio

Numbered list (1. 2. 3.) of specific considerations for the client's portfolio. Keep actionable and non-directive.

### 5. Advisory Considerations

Numbered checklist of suggested review actions. Non-directive and aligned with client risk profile.

### 6. Risks & Caveats

Brief bullet points on risks, uncertainty, and regulatory disclaimers.

---

## Additional Rules

- **DO NOT** collapse all content into one or two paragraphs. Every section must be present and separated by its `###` heading.
- **DO** bold key metrics (AUM, YTD, allocation percentages) wherever they appear.
- **DO** preserve any JSON chart objects from the specialist's output verbatim. They look like: `{ "type": "pie", "title": "...", "labels": [...], "values": [...] }`. Include them at the end of your response if present.
- **DO** extract key financial metrics (AUM, YTD, allocation %) into the structured `metrics` field.
- **DO** generate 3-5 relevant follow-up questions in the `follow_up_suggestions` field.
- **DO** assess whether human RM escalation is needed.
- **DO** maintain a professional, discreet, and analytical tone appropriate for HNWI clients.
- Never expose internal routing or agent names.
"""


def _build_synthesizer_llm():  # noqa: ANN202
    """Construct a Gemini LLM instance with structured output bound to SynthesizerOutput.

    Returns:
        A Runnable configured to return SynthesizerOutput.
    """
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.3,
        max_output_tokens=2000,
    )
    return llm.with_structured_output(SynthesizerOutput)


async def synthesizer_node(state: WorkflowState) -> dict:
    """Combine outputs from all executed agents into a final user-facing response.

    Uses Gemini structured output to produce a validated SynthesizerOutput
    that includes the response, confidence level, follow-up suggestions,
    and escalation flags.

    Args:
        state: The workflow state containing all agent outputs.

    Returns:
        A dictionary with the final synthesized response.
    """
    logger.info("synthesizer_node_start", output_count=len(state.agent_outputs))

    if not state.agent_outputs:
        return {
            "final_response": "I apologize, but I was unable to process your request. "
            "Please try again or contact your relationship manager for assistance."
        }

    if settings.is_llm_mock_mode:
        combined = "\n".join(output["result"] for output in state.agent_outputs)
        return {"final_response": f"[MOCK SYNTHESIS]\nBased on specialist input:\n{combined}"}

    structured_llm = _build_synthesizer_llm()

    agent_results_text = "\n\n".join(
        f"[Specialist {index + 1}]: {output['result']}"
        for index, output in enumerate(state.agent_outputs)
    )

    prompt = (
        f"Client's original query: {state.user_message}\n\n"
        f"Specialist results:\n{agent_results_text}\n\n"
        f"Synthesize these into a single helpful response for the client."
    )

    try:
        result = await structured_llm.ainvoke(
            [
                SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )

        response_text = result.response

        if result.requires_human_escalation:
            logger.info(
                "synthesizer_escalation_flagged",
                reason=result.escalation_reason,
            )

        logger.info(
            "synthesizer_node_complete",
            response_length=len(response_text),
            confidence=result.confidence,
            metrics_count=len(result.metrics),
        )
        return {
            "final_response": response_text,
            "final_metrics": [m.model_dump() for m in result.metrics],
            "final_suggestions": result.follow_up_suggestions,
        }

    except Exception:
        logger.exception("synthesizer_node_failed")
        return {
            "final_response": "I apologize, but I am unable to provide a detailed summary at "
            "this moment. Please rest assured that your request has been recorded, and you "
            "can contact your dedicated relationship manager for further information."
        }


def should_continue_executing(state: WorkflowState) -> str:
    """Determine whether there are more steps to execute or if synthesis should begin.

    Args:
        state: The current workflow state.

    Returns:
        The name of the next node: 'executor' or 'synthesizer'.
    """
    if state.plan is None:
        return "synthesizer"
    if state.current_step_index < len(state.plan.steps):
        return "executor"
    return "synthesizer"


def should_use_agents(state: WorkflowState) -> str:
    """Determine whether the plan requires agent execution or has a direct response.

    Args:
        state: The current workflow state with the planner output.

    Returns:
        The name of the next node: 'executor' or 'direct_response'.
    """
    if state.plan and not state.plan.requires_agent:
        return "direct_response"
    return "executor"


async def direct_response_node(state: WorkflowState) -> dict:
    """Return the planner's direct response without invoking any agents.

    Used for simple queries like greetings that don't need specialist routing.

    Args:
        state: The workflow state containing the planner's direct response.

    Returns:
        A dictionary with the final response.
    """
    response = state.plan.direct_response if state.plan else "How can I help you today?"
    return {"final_response": response}


async def escalation_check_node(state: WorkflowState) -> dict:
    """Check if the query should be escalated before planning.

    This is a lightweight passthrough node that allows the conditional
    edge to inspect the user message for escalation patterns.

    Args:
        state: The current workflow state.

    Returns:
        An empty dict (no state changes).
    """
    return {}


def should_escalate(state: WorkflowState) -> str:
    """Determine whether the query should be escalated to a human RM.

    Args:
        state: The current workflow state.

    Returns:
        The name of the next node: 'escalation' or 'planner'.
    """
    if check_escalation(state.user_message):
        return "escalation"
    return "planner"


def build_workflow_graph():  # noqa: ANN201
    """Construct the LangGraph state graph for the customer service workflow.

    The graph follows a plan-and-execute pattern with an escalation bypass:
        escalation_check -> [escalation -> END | planner -> executor (loop) -> synthesizer -> END]

    Returns:
        The compiled LangGraph StateGraph ready for invocation.
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("escalation_check", escalation_check_node)
    graph.add_node("escalation", escalation_node)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("direct_response", direct_response_node)

    graph.set_entry_point("escalation_check")

    graph.add_conditional_edges(
        "escalation_check",
        should_escalate,
        {"escalation": "escalation", "planner": "planner"},
    )

    graph.add_edge("escalation", END)
    graph.add_conditional_edges(
        "planner",
        should_use_agents,
        {"executor": "executor", "direct_response": "direct_response"},
    )

    graph.add_conditional_edges(
        "executor",
        should_continue_executing,
        {"executor": "executor", "synthesizer": "synthesizer"},
    )

    graph.add_edge("synthesizer", END)
    graph.add_edge("direct_response", END)

    return graph.compile()


workflow_graph = build_workflow_graph()


async def run_workflow(
    user_message: str,
    conversation_history: list[dict[str, str]],
    memory_context: list[dict],
    session_id: str,
    user_id: str,
) -> dict[str, str | dict | None]:
    """Execute the full agentic workflow for a user message.

    Args:
        user_message: The user's input message.
        conversation_history: Previous messages in the conversation.
        memory_context: Retrieved mem0 memory entries for context.
        session_id: The current chat session identifier.
        user_id: The authenticated user's identifier.

    Returns:
        A dictionary with 'response' (the final text) and optional 'trace' data.
    """
    logger.info(
        "workflow_start",
        session_id=session_id,
        user_id=user_id,
        message_length=len(user_message),
    )

    initial_state = WorkflowState(
        user_message=user_message,
        conversation_history=conversation_history,
        memory_context=memory_context,
        session_id=session_id,
        user_id=user_id,
    )

    try:
        final_state = await workflow_graph.ainvoke(initial_state)

        # Handle either string or Pydantic model (SynthesizerOutput)
        response = final_state["final_response"]

        trace_data = {
            "plan": final_state["plan"].model_dump() if final_state["plan"] else None,
            "agent_outputs": final_state["agent_outputs"],
        }

        logger.info("workflow_complete", session_id=session_id)

        return {
            "response": response,
            "metrics": final_state.final_metrics,
            "suggestions": final_state.final_suggestions,
            "trace": trace_data,
        }

    except Exception:
        logger.exception("workflow_failed", session_id=session_id)
        return {
            "response": "I apologize, but I encountered an error while processing your request. "
            "Please try again or contact your relationship manager.",
            "trace": None,
        }
