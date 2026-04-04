"""Shared state definitions for the LangGraph agentic workflow."""

from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from apps.api.customers.registry import DEFAULT_CUSTOMER_ID

# ---------------------------------------------------------------------------
# Structured output models for specialist MCP-server LLM calls
# ---------------------------------------------------------------------------


class ChartItem(BaseModel):
    """A chart object embedded in an agent response for frontend rendering."""

    type: str = Field(description="Chart type: pie, line, bar, or gauge")
    title: str = Field(description="Display title for the chart")
    labels: list[str] = Field(default_factory=list, description="Data labels")
    values: list[float] = Field(default_factory=list, description="Data values")
    badge: str | None = Field(default=None, description="Optional badge text (e.g. for gauge)")


class AllocationItem(BaseModel):
    """A single row in an asset-allocation breakdown."""

    asset_class: str = Field(description="Asset class label (e.g. Equities)")
    allocation_pct: float = Field(description="Percentage of total portfolio")
    value_sgd: float = Field(description="Absolute value in SGD")


class CurrencyExposureItem(BaseModel):
    """Currency exposure entry."""

    currency: str = Field(description="ISO currency code")
    value_sgd: float = Field(description="Value in SGD")


class LiquiditySummary(BaseModel):
    """Liquidity snapshot."""

    cash_sgd: float = Field(default=0.0, description="Cash position in SGD")
    available_credit_sgd: float = Field(default=0.0, description="Available credit in SGD")


class PortfolioAssessment(BaseModel):
    """Portfolio-level figures returned by the wealth-advisory agent."""

    total_value_sgd: float = Field(description="Total portfolio value in SGD")
    ytd_performance_pct: float = Field(description="Year-to-date return percentage")
    allocation_breakdown: list[AllocationItem] = Field(default_factory=list)
    currency_exposure: list[CurrencyExposureItem] = Field(default_factory=list)
    concentration_risks: list[str] = Field(default_factory=list)
    liquidity_summary: LiquiditySummary = Field(default_factory=LiquiditySummary)


class WealthAdvisoryOutput(BaseModel):
    """Structured output for the wealth-advisory LLM call."""

    summary: list[str] = Field(default_factory=list, description="Key takeaways")
    portfolio_assessment: PortfolioAssessment
    market_context: list[str] = Field(default_factory=list)
    implications: list[str] = Field(default_factory=list)
    advisory_considerations: list[str] = Field(default_factory=list)
    risks_and_caveats: list[str] = Field(default_factory=list)
    charts: list[ChartItem] = Field(default_factory=list)


class PrivateBankingFlags(BaseModel):
    """Security and approval flags for private-banking responses."""

    requires_verification: bool = Field(default=False)
    requires_rm_approval: bool = Field(default=False)


class PrivateBankingOutput(BaseModel):
    """Structured output for the private-banking LLM call."""

    intent: str = Field(description="Detected client intent")
    data: dict[str, Any] = Field(default_factory=dict, description="Response payload")
    flags: PrivateBankingFlags = Field(default_factory=PrivateBankingFlags)
    missing_fields: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, description="0.0–1.0 confidence score")


class ComplianceTaxOutput(BaseModel):
    """Structured output for the compliance-and-tax LLM call."""

    query_type: str = Field(description="e.g. Tax Reporting, AML/KYC, Cross-Border Documentation")
    guidance_summary: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    escalation_required: bool = Field(default=False)
    jurisdiction: str = Field(default="")
    next_steps: list[str] = Field(default_factory=list)
    notes: str = Field(default="")


# ---------------------------------------------------------------------------
# Workflow state models
# ---------------------------------------------------------------------------


class AgentStep(BaseModel):
    """A single planned step to be executed by a specialized agent."""

    agent: str = Field(description="The agent responsible for this step")
    task: str = Field(description="The specific task for the agent to perform")
    completed: bool = Field(default=False, description="Whether this step has been executed")
    result: str | None = Field(default=None, description="The result after execution")


class MetricItem(BaseModel):
    """A key-value pair representing a financial metric."""

    label: str = Field(description="The display label for the metric (e.g. AUM)")
    value: str = Field(description="The numeric or text value of the metric")
    trend: str | None = Field(
        default=None, description="Optional trend indicator: up, down, or neutral"
    )


class PlannerOutput(BaseModel):
    """The structured output from the planner node."""

    reasoning: str = Field(description="The planner's reasoning about how to handle the query")
    steps: list[AgentStep] = Field(description="The ordered list of steps to execute")
    requires_agent: bool = Field(
        default=True,
        description="Whether the query requires agent execution or can be answered directly",
    )
    direct_response: str | None = Field(
        default=None,
        description="A direct response if no agent execution is needed",
    )


class SynthesizerOutput(BaseModel):
    """The structured output from the synthesizer node."""

    response: str = Field(
        description=(
            "The synthesized client-facing response in Markdown or concise prose, dynamically"
            " shaped by query complexity. "
            "For simple single-question asks, a short direct answer is allowed without section"
            " headers. "
            "For multi-part/advisory asks, use relevant ### sections only (e.g., Summary, Next"
            " Steps, Important Notes). "
            "Add specialist sections (### Service Status, ### Credit & Lending Summary, etc.)"
            " only when relevant. "
            "Never include empty/placeholder sections. "
            "Bold key figures (AUM, YTD, amounts, dates) wherever they appear."
        )
    )
    confidence: str = Field(description="Confidence level in the response: high, medium, or low")
    metrics: list[MetricItem] = Field(
        default_factory=list,
        description="Key metrics extracted from specialist analysis",
    )
    follow_up_suggestions: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions the client might ask",
    )
    requires_human_escalation: bool = Field(
        default=False,
        description="Whether this query should be escalated to a human relationship manager",
    )
    escalation_reason: str | None = Field(
        default=None,
        description="Reason for escalation if requires_human_escalation is true",
    )


class WorkflowState(BaseModel):
    """The complete state object threaded through the LangGraph workflow.

    This state is passed between all nodes in the graph and accumulates
    results as agents execute their assigned steps.
    """

    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    user_message: str = Field(description="The original user query (may include file context)")
    escalation_text: str = Field(
        default="", description="Raw user text for escalation checks (excludes file content)"
    )
    conversation_history: list[dict[str, str]] = Field(default_factory=list)
    memory_context: list[dict] = Field(default_factory=list)
    session_id: str = Field(default="")
    user_id: str = Field(default="")
    customer_id: str = Field(default=DEFAULT_CUSTOMER_ID)
    plan: PlannerOutput | None = Field(default=None, description="The execution plan")
    current_step_index: int = Field(default=0, description="Index of the step being executed")
    agent_outputs: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Collected outputs from each agent execution",
    )
    final_response: str = Field(default="", description="The synthesized final response")
    final_metrics: list[MetricItem] = Field(
        default_factory=list, description="Structured metrics for dashboard rendering"
    )
    final_suggestions: list[str] = Field(
        default_factory=list, description="Suggested follow-up questions"
    )
    is_escalated: bool = Field(
        default=False, description="Whether the query was escalated to a human RM"
    )
    error: str | None = Field(default=None, description="Error message if workflow fails")
