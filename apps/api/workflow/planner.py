"""Planner node for the LangGraph workflow.

Analyzes the user query and conversation context to produce a structured
execution plan that routes to the appropriate specialist agents for
UBS Wealth Management HNWI client support.

Uses Gemini structured output to guarantee a valid PlannerOutput schema.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.state import AgentStep, PlannerOutput, WorkflowState

logger = get_logger(__name__)

PLANNER_SYSTEM_PROMPT = """You are a customer service routing planner for UBS Wealth Management,
serving High Net Worth Individual (HNWI) clients. Your job is to route each query to the
correct specialist agent — or handle it directly without agents when appropriate.

---

## ROUTING RULES

Route to an agent ONLY when the query clearly matches that agent's specific domain.
Do NOT route to wealth_advisory as a catch-all or default.

### wealth_advisory
Route here ONLY for: portfolio performance, YTD/annual returns, asset allocation,
investment strategy, market outlook, structured products, AUM, portfolio value,
concentration risk, or alternative investments.
Examples: "How is my portfolio doing?", "What is my YTD return?", "Show me my allocation"

### private_banking
Route here ONLY for: account balances, fund transfers, card services, account statements,
transaction history, cheque requests, multi-currency accounts, or general banking ops.
Examples: "What's my balance?", "Transfer funds", "Show my transactions"

### lending_credit
Route here ONLY for: Lombard loans, mortgage financing, credit lines, overdraft facilities,
margin lending, borrowing capacity, or credit covenant monitoring.
Examples: "How much can I borrow?", "Tell me about my Lombard loan", "Credit facility status"

### compliance_tax
Route here ONLY for: CRS/FATCA tax reporting, source-of-wealth documentation, withholding
tax, cross-border tax certificates, or regulatory compliance queries.
Examples: "What are my CRS obligations?", "Help with FATCA filing", "Source of wealth docs"

### fx_treasury
Route here ONLY for: FX transactions or quotes, currency hedging, forward contracts, FX
market rates, large currency conversions, or treasury/cash pooling.
Examples: "Convert USD to SGD", "Hedge my FX exposure", "What's the EUR/SGD rate?"

### client_services
Route here ONLY for: KYC/AML document refresh, appointment scheduling with RM or specialists,
new account onboarding, document requests (tax certificates, audit letters), or service
escalation tracking.
Examples: "Schedule a meeting with my RM", "Submit KYC documents", "Request an audit letter"

---

## DIRECT RESPONSE — When NOT to use agents

Set `requires_agent` to `false` and put the full reply in `direct_response` for:

1. **Greetings** (Hello, Hi, Good morning, etc.)
   - Warm professional UBS welcome.
   - Briefly mention the 3 key service areas: Portfolio & Insights, Account & Banking,
     Lending & Credit.
   - Keep it to 2-3 sentences max.

2. **Thank-you or sign-off messages** (Thanks, Goodbye, etc.)
   - Short warm acknowledgement in 1 sentence. Offer to help with anything else.

3. **Genuinely ambiguous queries where the topic is completely unclear**
   - Use this sparingly — only when no agent can help without more information.
   - Ask exactly ONE short clarifying question in a warm UBS tone.
   - Do NOT ask multiple sub-questions.
   - Example: "Could you let me know what you'd like help with — your portfolio,
     an account matter, a loan, or something else?"
   - If conversation history already provides enough context, DO NOT ask — route instead.

---

## AMBIGUITY THRESHOLD

Prefer routing over asking. Ask for clarification ONLY when intent is completely impossible
to infer (e.g., "help me", "I have a question", "tell me something"). If intent is even
60% clear from the query or conversation history, route to the most appropriate agent.
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

    # Simple heuristic for very short greetings to save LLM tokens if possible
    # but the prompt already handles it, so we let the structured LLM handle it
    # to ensure the direct_response matches the UBS tone.

    if settings.is_llm_mock_mode:
        logger.info("planner_mock_mode")
        plan = PlannerOutput(
            reasoning="Query requires client services support.",
            steps=[AgentStep(agent="client_services", task=state.user_message)],
            requires_agent=True,
        )
        return {"plan": plan, "current_step_index": 0}

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
        plan = await structured_llm.ainvoke(
            [
                SystemMessage(content=PLANNER_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
        )

        logger.info(
            "planner_node_complete",
            requires_agent=plan.requires_agent,
            step_count=len(plan.steps),
        )

    except Exception as error:
        logger.exception("planner_structured_output_failed", error=str(error))
        plan = PlannerOutput(
            reasoning="Could not produce structured plan, routing to client services as default.",
            steps=[AgentStep(agent="client_services", task=state.user_message)],
            requires_agent=True,
        )

    return {"plan": plan, "current_step_index": 0}
