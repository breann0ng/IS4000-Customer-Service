"""Planner node for the LangGraph workflow.

Analyzes the user query and conversation context to produce a structured
execution plan that routes to the appropriate specialist agents for
UBS Wealth Management HNWI client support.

Uses Gemini structured output to guarantee a valid PlannerOutput schema.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from apps.api.config import resiliency_manager, settings
from apps.api.logging_config import get_logger
from apps.api.workflow.state import AgentStep, PlannerOutput, WorkflowState

logger = get_logger(__name__)

PLANNER_SYSTEM_PROMPT = """You are a customer service routing planner for UBS Wealth Management,
handling queries from High Net Worth Individual (HNWI) clients. Analyze the client's query
and conversation history to determine which specialist agents should handle the request.

Available agents:

- wealth_advisory: Portfolio performance reviews, investment strategy recommendations,
  market insights and economic outlook, asset allocation optimization, structured products,
  alternative investments, estate planning, and intergenerational wealth transfer

- private_banking: Account balance inquiries and operations, fund transfers (domestic and
  cross-border), card services and premium card management, account statements and reporting,
  multi-currency account management, and general banking operations

- client_services: New client onboarding, KYC/AML documentation and refresh processes,
  document requests (tax certificates, audit letters), appointment scheduling with
  relationship managers and specialists, service escalations and complaint resolution,
  and general service status tracking

- lending_credit: Lombard lending against investment portfolios, mortgage financing
  (residential and commercial), revolving credit lines and overdraft facilities,
  structured lending solutions, margin facilities for leveraged strategies, and
  credit facility monitoring and covenant management

- compliance_tax: Tax reporting obligations (CRS, FATCA, jurisdiction-specific),
  cross-border tax documentation and withholding tax reclaims, regulatory change impacts,
  source-of-wealth documentation, tax-efficient investment structuring guidance,
  estate and inheritance tax across jurisdictions, and regulatory compliance updates

- fx_treasury: Foreign exchange transactions and quotes, currency hedging strategies,
  FX market insights and rate analysis, forward contracts and FX options structuring,
  large currency conversion execution, treasury management and cash pooling,
  and cross-currency payment flow optimization

For each query, determine:
1. Whether it requires specialized agent routing.
2. Which agents are needed and in what order (use multiple when the query spans domains)
3. What specific task each agent should perform

For greetings (e.g., "Hello", "Hi"):
- Set `requires_agent` to `false`.
- Provide a warm, premium welcome in `direct_response` and introduce our services.
- Explicitly mention the 3 most common use cases:
  1. Portfolio Performance & Insights (Wealth Advisory)
  2. Account Balances & Transactions (Private Banking)
  3. Lombard Lending & Credit Options (Lending & Credit)
"""


def _build_planner_llm():  # noqa: ANN202
    """Construct a Gemini LLM instance with structured output bound to PlannerOutput.

    Returns:
        A Runnable configured to return PlannerOutput.
    """
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.0,
        max_output_tokens=2048,
        max_retries=0,  # Fail fast! Let our own resiliency logic handle fallbacks.
    )
    return llm.with_structured_output(PlannerOutput)


async def planner_node(state: WorkflowState) -> dict:
    """Analyze the user query and produce an execution plan.

    Uses Gemini structured output to directly parse the LLM response
    into a validated PlannerOutput Pydantic model, eliminating manual
    JSON parsing and its associated failure modes.

    Args:
        state: The current workflow state containing the user message
            and conversation history.

    Returns:
        A dictionary with the updated plan to merge into the workflow state.
    """
    logger.info("planner_node_start", user_message=state.user_message[:100])

    # 1. Check Circuit Breaker
    if resiliency_manager.is_circuit_breaker_tripped:
        logger.warning("planner_circuit_breaker_tripped_skipping_llm")
        return _planner_fallback(state, "Circuit breaker active - using keyword fallback.")

    # 2. Check Mock Mode
    if settings.is_llm_mock_mode:
        logger.info("planner_mock_mode_routing")
        return _planner_fallback(state, "Mock mode routing active.")

    structured_llm = _build_planner_llm()

    memory_summary = ""
    if state.memory_context:
        memory_entries = [
            entry.get("memory", entry.get("text", ""))
            for entry in state.memory_context
            if isinstance(entry, dict)
        ]
        if memory_entries:
            memory_summary = "\n\nRelevant client context from memory:\n" + "\n".join(
                memory_entries
            )

    history_text = ""
    if state.conversation_history:
        recent_messages = state.conversation_history[-10:]
        history_text = "\n\nRecent conversation:\n" + "\n".join(
            f"{message['role']}: {message['content']}" for message in recent_messages
        )

    user_prompt = (
        f"Client query: {state.user_message}"
        f"{history_text}"
        f"{memory_summary}"
        f"\n\nProduce a plan to handle this query."
    )

    try:
        # Fail fast! Only 1 attempt before falling back to manual routing
        retryer = AsyncRetrying(
            stop=stop_after_attempt(1),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )

        async for attempt in retryer:
            with attempt:
                plan = await structured_llm.ainvoke(
                    [
                        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
                        HumanMessage(content=user_prompt),
                    ]
                )
        
        resiliency_manager.record_success()
        logger.info(
            "planner_node_complete",
            requires_agent=plan.requires_agent,
            step_count=len(plan.steps),
        )
        return {"plan": plan, "current_step_index": 0}

    except Exception as error:
        resiliency_manager.record_failure(str(error))
        logger.exception("planner_node_failed_using_fallback", error=str(error))
        return _planner_fallback(state, f"Planner error: {str(error)}")


def _planner_fallback(state: WorkflowState, reasoning: str) -> dict:
    """Implement keyword-based routing as a robust fallback for the planner."""
    query = state.user_message.lower()
    
    if any(w in query for w in ["lombard", "loan", "limit", "credit", "borrow"]):
        agent = "lending_credit"
        reasoning += " (Detected: lending/credit)"
    elif any(w in query for w in ["portfolio", "performance", "invest", "allocation", "equity", "bond"]):
        agent = "wealth_advisory"
        reasoning += " (Detected: wealth advisory)"
    elif any(w in query for w in ["cash", "balance", "account", "transfer", "transaction", "sgd", "usd", "eur", "chf"]):
        agent = "private_banking"
        reasoning += " (Detected: private banking)"
    elif any(w in query for w in ["tax", "compliance", "regulatory", "kyc", "onboard"]):
        agent = "client_services"
        reasoning += " (Detected: client services)"
    else:
        agent = "client_services"
        reasoning += " (Defaulted to client services)"

    plan = PlannerOutput(
        reasoning=reasoning,
        steps=[AgentStep(agent=agent, task=state.user_message)],
        requires_agent=True,
    )
    return {"plan": plan, "current_step_index": 0}
