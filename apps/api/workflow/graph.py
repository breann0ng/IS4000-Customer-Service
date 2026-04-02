"""LangGraph workflow definition for the customer service chatbot.

Implements a plan-and-execute pattern where:
1. The planner analyzes the user query and creates an execution plan
2. The executor dispatches steps to specialist agents
3. A synthesizer combines all results into a final response

All LLM calls use Gemini with structured outputs via Pydantic models.
"""

import json
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from apps.api.config import resiliency_manager, settings
from apps.api.logging_config import get_logger
from apps.api.workflow.escalation import check_escalation, escalation_node
from apps.api.workflow.executor import executor_node
from apps.api.workflow.planner import planner_node
from apps.api.workflow.state import SynthesizerOutput, WorkflowState

logger = get_logger(__name__)

SYNTHESIZER_SYSTEM_PROMPT = """You are a private wealth management assistant for UBS, serving High Net Worth Individual (HNWI) clients.
You receive structured analysis from specialist agents who have processed the client's query.

### GUIDELINES:
1. **Response Structure**: Use strict Markdown formatting with `###` section headers. 
   - ALWAYS include `### Summary`, `### Next Steps`, and `### Important Notes`.
   - Add `### Portfolio Overview`, `### Market Context`, or `### Strategic Outlook` ONLY if relevant data (AUM, exposure, asset classes) is provided.
2. **Executive Summary**: Start with a `### Summary` section (2-3 sentences) with bold key figures.
3. **Actionable Next Steps**: Provide a `### Next Steps` numbered list.
4. **Visuals**: If `raw_data` contains chart definitions, include them as JSON at the very end.
5. **Human Escalation**: If any agent flags `requires_escalation`, mention that the RM has been notified.

### CONTROLS:
- **No Blocks**: Do NOT write a single prose paragraph; every section must be separated by its `###` heading.
- **Bold Figures**: **Bold** all financial figures, dates, and percentages (e.g., **5.2%**, **USD 10M**, **April 2026**).
- **No Hallucinations**: If an agent reports an error, apologize for the technical interruption. Do NOT use unrelated policy documents.
- **Confidence Level**: Always provide a `confidence` level (high, medium, or low).
- Do NOT expose internal agent names or technical JSON keys.

Your job is to synthesize these results into a single, polished, and empathetic client-facing response.
"""


METADATA_EXTRACTION_PROMPT = """Analyze the following assistant response and the background agent data.
Extract structured metadata according to the schema:
1. **Confidence**: High, Medium, or Low based on the agent findings.
2. **Metrics**: Extract any key financial figures (AUM, USD values, rates, dates) as a list of metric items.
3. **Suggestions**: Generate 2-3 logical follow-up questions the client might ask next based on their portfolio context.
"""


def format_agent_outputs(outputs: list[dict]) -> str:
    """Helper to convert agent output list into a formatted string for the synthesizer."""
    parts = []
    for out in outputs:
        agent = out.get("agent", "Specialist").replace("_", " ").title()
        res = out.get("result")
        # Handle Pydantic models or raw strings
        res_text = res.response if hasattr(res, "response") else str(res)
        parts.append(f"### {agent}\n{res_text}")
    return "\n\n".join(parts)


def _build_synthesizer_llm():  # noqa: ANN202
    """Construct a Gemini LLM instance with structured output bound to SynthesizerOutput.

    Returns:
        A Runnable configured to return SynthesizerOutput.
    """
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.3,
        max_output_tokens=4000,
        max_retries=0,  # Fail fast!
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

    # 1. Check Circuit Breaker
    if resiliency_manager.is_circuit_breaker_tripped:
        logger.warning("synthesizer_circuit_breaker_tripped_skipping_llm")
        return _synthesizer_fallback(state, "Circuit breaker active - using raw data synthesis.")

    # 2. Check Mock Mode
    if settings.is_llm_mock_mode:
        combined_parts = []
        for output in state.agent_outputs:
            agent_name = output.get('agent', 'Specialist').replace('_', ' ').title()
            result = output.get('result')
            # Extract response text if it's a model, otherwise use as string
            res_text = result.response if hasattr(result, 'response') else str(result)
            combined_parts.append(f"### {agent_name}\n{res_text}")
        
        combined = "\n\n".join(combined_parts)
        return {"final_response": f"[MOCK SYNTHESIS]\nBased on specialist input:\n\n{combined}"}


    structured_llm = _build_synthesizer_llm()

    agent_results_text = "\n\n".join(
        f"[Agent: {output.get('agent', 'Specialist')}]\n{output['result'].model_dump_json(indent=2) if hasattr(output['result'], 'model_dump_json') else output['result']}"
        for output in state.agent_outputs
    )

    prompt = (
        f"Original query: {state.user_message}\n\n"
        f"Specialist findings:\n{agent_results_text}\n\n"
        f"Synthesize the findings into a premium response."
    )

    try:
        # Check for empty results before starting
        agent_outputs = state.agent_outputs
        if not agent_outputs:
            return {
                "final_response": "I couldn't find any specific information related to your request. How else can I assist you?",
                "final_metrics": [],
                "final_suggestions": [],
            }

        # Fail fast! Only 1 attempt before falling back to manual raw-data synthesis
        retryer = AsyncRetrying(
            stop=stop_after_attempt(1),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )

        # Step 1: Generate the full Markdown response (Standard LLM)
        standard_llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.3,
            max_output_tokens=4000,
            max_retries=0,
        )

        agent_data_summary = format_agent_outputs(agent_outputs)
        # raw_data is not in WorkflowState BaseModel, skipping or use empty dict
        raw_data_json = json.dumps({})
        
        prompt_text = f"AGENT DATA:\n{agent_data_summary}\n\nRAW DATA:\n{raw_data_json}"

        async for attempt in retryer:
            with attempt:
                # Step 1: Writing the Markdown Response
                writing_result = await standard_llm.ainvoke(
                    [
                        SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
                        HumanMessage(content=prompt_text),
                    ]
                )
        
        final_markdown = writing_result.content

        # Step 2: Extract Structured Metadata (Structured LLM)
        structured_llm = _build_synthesizer_llm()
        
        metadata_prompt = f"ASSISTANT RESPONSE:\n{final_markdown}\n\n{prompt_text}"

        async for attempt in retryer:
            with attempt:
                metadata_result = await structured_llm.ainvoke(
                    [
                        SystemMessage(content=METADATA_EXTRACTION_PROMPT),
                        HumanMessage(content=metadata_prompt),
                    ]
                )

        resiliency_manager.record_success()

        logger.info(
            "synthesizer_decomposed_complete",
            response_length=len(final_markdown),
            confidence=getattr(metadata_result, "confidence", "unknown"),
        )

        return {
            "final_response": final_markdown,
            "final_metrics": [m.model_dump() if hasattr(m, "model_dump") else m for m in getattr(metadata_result, "metrics", [])],
            "final_suggestions": getattr(metadata_result, "follow_up_suggestions", []),
        }

    except Exception as e:
        resiliency_manager.record_failure(str(e))
        logger.exception("synthesizer_decomposed_failed_using_fallback", error=str(e))
        return _synthesizer_fallback(state, f"Synthesis error: {str(e)}")


def _synthesizer_fallback(state: WorkflowState, error_msg: str) -> dict:
    """Implement a manual summary from agent outputs as a robust fallback."""
    fallback_parts = [
        "### Summary (Resiliency Mode)", 
        f"Our AI synthesis service is temporarily unavailable ({error_msg}). However, your requested data has been successfully retrieved from our core systems:"
    ]
    
    # Track metrics for the UI
    final_metrics = []

    for output in state.agent_outputs:
        result = output.get('result')
        if not result:
            continue

        # If it's the new SpecialistAgentOutput model
        if hasattr(result, 'response'):
            agent_label = result.agent_name.replace('_', ' ').title()
            fallback_parts.append(f"**[{agent_label}]**\n{result.response}")
            
            # Collect metrics
            if hasattr(result, 'metrics') and result.metrics:
                for m in result.metrics:
                    final_metrics.append({"label": m.label, "value": m.value, "trend": m.trend})
            
            # Add next steps
            if result.next_steps:
                fallback_parts.append("**Recommended Next Steps:**")
                for step in result.next_steps:
                    fallback_parts.append(f"- {step}")

    fallback_parts.append("\n### Important Notice\nYour relationship manager has been notified of this request. Please refresh in a moment for a more detailed analysis.")
    
    return {
        "final_response": "\n\n".join(fallback_parts),
        "final_metrics": final_metrics,
        "final_suggestions": ["Why is this message appearing?", "Try again in 1 minute"]
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
    username: str,
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
        username=username,
        message_length=len(user_message),
    )

    initial_state = WorkflowState(
        user_message=user_message,
        conversation_history=conversation_history,
        memory_context=memory_context,
        session_id=session_id,
        user_id=user_id,
        username=username,
    )

    try:
        final_state = await workflow_graph.ainvoke(initial_state)

        # Access attributes directly since final_state is a WorkflowState Pydantic model
        response = getattr(final_state, "final_response", "No response generated.")
        
        plan_data = getattr(final_state, "plan", None)
        if hasattr(plan_data, "model_dump"):
            plan_data = plan_data.model_dump()

        trace_data = {
            "plan": plan_data,
            "agent_outputs": getattr(final_state, "agent_outputs", []),
        }

        logger.info("workflow_complete", session_id=session_id)

        return {
            "response": response,
            "metrics": getattr(final_state, "final_metrics", []),
            "suggestions": getattr(final_state, "final_suggestions", []),
            "trace": trace_data,
        }

    except Exception as e:
        logger.exception("workflow_failed", session_id=session_id)
        # Return the actual error in the response for direct debugging by the user
        return {
            "response": f"DEBUG ERROR: {type(e).__name__} - {str(e)}\n\nPlease try one more time or report this specific error.",
            "trace": None,
        }
