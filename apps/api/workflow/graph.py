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
from apps.api.customers.registry import DEFAULT_CUSTOMER_ID
from apps.api.logging_config import get_logger
from apps.api.workflow.escalation import check_escalation, escalation_node
from apps.api.workflow.executor import executor_node
from apps.api.workflow.planner import planner_node
from apps.api.workflow.state import SynthesizerOutput, WorkflowState

logger = get_logger(__name__)

SYNTHESIZER_SYSTEM_PROMPT = """You are a private wealth management assistant for UBS, serving
High Net Worth Individual (HNWI) clients.
You receive structured JSON outputs from specialist agents who have analyzed the client's query.

Your job is to synthesize these JSON results into a single, polished, client-facing response.

---

## STEP 1 — Parse the Agent JSON

Each specialist result is a JSON string. You MUST read and interpret every field in the JSON
before writing your response.
Do NOT treat the JSON as literal text to paste — extract the meaningful data from it.

---

## STEP 2 — Choose Response Shape Dynamically

Choose the response format based on query complexity and agent data richness.

### For simple queries (single factual ask, status check, one direct question):
- Prefer a concise direct answer (1–3 short paragraphs or bullets).
- Do NOT force section headers.
- Include only what is relevant; omit empty or generic blocks.

### For multi-part or advisory queries:
- Use Markdown `###` section headers.
- Include only sections that are relevant to the actual agent output.
- Do NOT include placeholder sections.

### Core optional sections (use only when relevant):
- `### Summary` — concise executive synthesis.
- `### Next Steps` — actionable items when there are genuine actions.
- `### Important Notes` — caveats/disclaimers only when applicable.

### Include ONLY if the agent data contains portfolio or financial metrics
### (e.g., AUM, YTD return, asset allocation):
- `### Portfolio Overview` — Reference EXACT figures from the agent JSON: **AUM**, **YTD return**,
  allocation breakdown. Bold all key numbers. Do NOT invent or estimate values — copy them
  verbatim from the agent data.
- `### Market Context` — Bullet points on relevant macro conditions, sector trends, or economic
  drivers.
- `### Considerations` — Non-directive numbered list of portfolio implications for the client.

### Include ONLY for lending/credit queries:
- `### Credit & Lending Summary` — Facility type, borrowing capacity, LTV range, and key
  constraints.

### Include ONLY for FX/treasury queries:
- `### FX & Treasury Insights` — Relevant rates, hedging strategies, risk analysis.

### Include ONLY for compliance/tax queries:
- `### Compliance & Tax Guidance` — Regulatory obligations, required documents, jurisdiction.

### Include ONLY for service/onboarding queries:
- `### Service Status` — Request type, current status, required documents, assigned team,
  estimated timeline.

---

## STEP 3 — Charts

If any agent's JSON contains a `"charts"` array, include each chart object verbatim at the end
of the response.
Charts look like: `{ "type": "pie", "title": "...", "labels": [...], "values": [...] }`
Include them as bare JSON objects (not in code fences) at the very end of your response text.

---

## STEP 4 — Metrics Field

Populate the `metrics` field ONLY when the agent data contains concrete financial figures such as
AUM, YTD return, borrowing capacity, portfolio value, or account balances.
Do NOT populate `metrics` for operational queries (status checks, document requests, appointments,
compliance guidance) unless a specific monetary figure is directly relevant.

---

## Rules

- **DO** adapt structure and length to the question complexity.
- **DO** bold all key figures (AUM, YTD, amounts, percentages, dates).
- **DO** generate 3–5 relevant follow-up questions in `follow_up_suggestions`.
- **DO** assess whether human RM escalation is needed based on `escalation_required` or
  `requires_rm_approval` flags in the JSON.
- **DO** maintain a professional, discreet, and empathetic tone appropriate for HNWI clients.
- **DO NOT** expose internal agent names, routing details, or raw JSON field names in the
  client-facing response.
- **DO NOT** fabricate data — only use information present in the specialist JSON.
- **CRITICAL — DATA ACCURACY**: You MUST use the EXACT numerical values from the specialist agent
  JSON outputs for AUM, YTD return, allocation percentages, dollar amounts, and all other
  financial figures. NEVER estimate, round differently, or generate your own figures. If the agent
  JSON says total_value_sgd is 65000000, report exactly SGD 65,000,000 — do not invent a different
  number like 87.1M. Every financial figure in your response must be directly traceable to the
  agent JSON data.
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
        f"[{output.get('agent', f'Specialist {index + 1}')} JSON result]:\n{output['result']}"
        for index, output in enumerate(state.agent_outputs)
    )

    # Extract verified financial data from agent outputs to create a binding constraint
    import json as _json

    verified_facts = []
    for output in state.agent_outputs:
        try:
            parsed = _json.loads(output.get("result", ""))
            if isinstance(parsed, dict):
                pa = parsed.get("portfolio_assessment", {})
                if pa.get("total_value_sgd"):
                    verified_facts.append(
                        f"Total Portfolio Value: SGD {pa['total_value_sgd']:,.0f}"
                    )
                if pa.get("ytd_performance_pct") is not None:
                    verified_facts.append(f"YTD Return: {pa['ytd_performance_pct']}%")
                for item in pa.get("allocation_breakdown", []):
                    verified_facts.append(
                        f"{item['asset_class']}: {item['allocation_pct']}%"
                        f" (SGD {item['value_sgd']:,.0f})"
                    )
        except (ValueError, TypeError, KeyError):
            pass

    verified_section = ""
    if verified_facts:
        verified_section = (
            "\n\n=== VERIFIED FINANCIAL DATA (USE THESE EXACT NUMBERS) ===\n"
            + "\n".join(verified_facts)
            + "\n=== END VERIFIED DATA ===\n"
            "You MUST use the exact figures above. Do NOT use any other numbers for these"
            " metrics.\n"
        )

    prompt = (
        f"Client's original query: {state.user_message}\n\n"
        f"Specialist agent JSON outputs:\n{agent_results_text}\n\n"
        f"{verified_section}"
        f"Parse each JSON result and synthesize them into a single client-facing response "
        f"following the output format instructions above."
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

    Uses escalation_text (raw user input without file context) so that
    attached document content does not trigger false escalations.

    Args:
        state: The current workflow state.

    Returns:
        The name of the next node: 'escalation' or 'planner'.
    """
    text = state.escalation_text or state.user_message
    if check_escalation(text):
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
    customer_id: str = DEFAULT_CUSTOMER_ID,
    escalation_text: str = "",
) -> dict[str, str | dict | None]:
    """Execute the full agentic workflow for a user message.

    Args:
        user_message: The user's input message (may include file context).
        conversation_history: Previous messages in the conversation.
        memory_context: Retrieved mem0 memory entries for context.
        session_id: The current chat session identifier.
        user_id: The authenticated user's identifier.
        customer_id: The customer profile identifier.
        escalation_text: Raw user text for escalation checks (excludes file content).

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
        escalation_text=escalation_text or user_message,
        conversation_history=conversation_history,
        memory_context=memory_context,
        session_id=session_id,
        user_id=user_id,
        customer_id=customer_id,
    )

    try:
        final_state = await workflow_graph.ainvoke(initial_state)

        # Handle either string or Pydantic model (SynthesizerOutput)
        response = final_state.get("final_response", "")

        trace_data = {
            "plan": final_state["plan"].model_dump() if final_state.get("plan") else None,
            "agent_outputs": final_state.get("agent_outputs", []),
        }

        logger.info("workflow_complete", session_id=session_id)

        return {
            "response": response,
            "metrics": final_state.get("final_metrics", []),
            "suggestions": final_state.get("final_suggestions", []),
            "trace": trace_data,
        }

    except Exception:
        logger.exception("workflow_failed", session_id=session_id)
        return {
            "response": "I apologize, but I encountered an error while processing your request. "
            "Please try again or contact your relationship manager.",
            "trace": None,
        }
