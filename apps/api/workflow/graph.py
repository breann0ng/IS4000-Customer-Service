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
from apps.api.workflow.executor import executor_node
from apps.api.workflow.planner import planner_node
from apps.api.workflow.state import SynthesizerOutput, WorkflowState

logger = get_logger(__name__)

SYNTHESIZER_SYSTEM_PROMPT = """You are a private wealth management assistant for UBS,
serving High Net Worth Individual (HNWI) clients. You are given the results from
multiple specialist teams who have worked on different aspects of the client's query.
Synthesize these results into a single, coherent, and polished response.

Maintain the tone expected in premium private banking: professional, discreet,
and attentive. Address the client respectfully and provide actionable next steps
where appropriate. If any specialist encountered issues, acknowledge the limitation
gracefully and offer alternatives. Never expose internal routing, agent names,
or technical implementation details.

Also assess whether this query should be escalated to a human relationship manager
(for example, if the request involves high-risk decisions, complaints, or topics
where automated responses are insufficient).
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
        max_output_tokens=4096,
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
        logger.info("synthesizer_mock_mode", reason="no gemini api key configured")
        combined = "\n\n".join(output["result"] for output in state.agent_outputs)
        response_text = (
            f"[MOCK] Here is a summary of results for your query:\n\n{combined}"
            "\n\nYou might also want to ask about:"
            "\n- Account balance details\n- Recent transactions"
        )
        return {"final_response": response_text}

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
        if result.follow_up_suggestions:
            response_text += "\n\nYou might also want to ask about:\n" + "\n".join(
                f"- {suggestion}" for suggestion in result.follow_up_suggestions
            )
        if result.requires_human_escalation:
            response_text += (
                "\n\nI would recommend connecting you with your dedicated relationship "
                "manager for further assistance on this matter."
            )
            logger.info(
                "synthesizer_escalation_flagged",
                reason=result.escalation_reason,
            )

        logger.info(
            "synthesizer_node_complete",
            response_length=len(response_text),
            confidence=result.confidence,
        )
        return {"final_response": response_text}

    except Exception:
        logger.exception("synthesizer_node_failed")
        combined = "\n".join(output["result"] for output in state.agent_outputs)
        return {"final_response": combined}


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


def build_workflow_graph():  # noqa: ANN201
    """Construct the LangGraph state graph for the customer service workflow.

    The graph follows a plan-and-execute pattern:
        planner -> [executor (loop) | direct_response] -> synthesizer -> END

    Returns:
        The compiled LangGraph StateGraph ready for invocation.
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("direct_response", direct_response_node)

    graph.set_entry_point("planner")

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

        trace_data = {
            "plan": final_state.get("plan").model_dump() if final_state.get("plan") else None,
            "agent_outputs": final_state.get("agent_outputs", []),
        }

        logger.info("workflow_complete", session_id=session_id)

        return {
            "response": final_state.get(
                "final_response", "I'm sorry, I couldn't generate a response."
            ),
            "trace": trace_data,
        }

    except Exception:
        logger.exception("workflow_failed", session_id=session_id)
        return {
            "response": "I apologize, but I encountered an error while processing your request. "
            "Please try again or contact your relationship manager.",
            "trace": None,
        }
