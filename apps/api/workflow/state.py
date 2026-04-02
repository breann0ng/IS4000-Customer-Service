"""Shared state definitions for the LangGraph agentic workflow."""

from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from apps.api.customers.registry import DEFAULT_CUSTOMER_ID


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
            "The synthesized client-facing response in Markdown or concise prose, dynamically shaped by query complexity. "
            "For simple single-question asks, a short direct answer is allowed without section headers. "
            "For multi-part/advisory asks, use relevant ### sections only (e.g., Summary, Next Steps, Important Notes). "
            "Add specialist sections (### Service Status, ### Credit & Lending Summary, etc.) only when relevant. "
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
    user_message: str = Field(description="The original user query")
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
