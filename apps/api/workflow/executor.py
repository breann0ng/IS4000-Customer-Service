"""Executor node for the LangGraph workflow.

Dispatches planned steps to the appropriate specialist agents and
collects their results for UBS Wealth Management HNWI support.
"""

from apps.api.logging_config import get_logger
from apps.api.workflow.agents.client_services import execute_client_services_task
from apps.api.workflow.agents.compliance_tax import execute_compliance_tax_task
from apps.api.workflow.agents.fx_treasury import execute_fx_treasury_task
from apps.api.workflow.agents.lending_credit import execute_lending_credit_task
from apps.api.workflow.agents.private_banking import execute_private_banking_task
from apps.api.workflow.agents.wealth_advisory import execute_wealth_advisory_task
from apps.api.workflow.state import WorkflowState

logger = get_logger(__name__)

AGENT_DISPATCH_TABLE = {
    "wealth_advisory": execute_wealth_advisory_task,
    "private_banking": execute_private_banking_task,
    "client_services": execute_client_services_task,
    "lending_credit": execute_lending_credit_task,
    "compliance_tax": execute_compliance_tax_task,
    "fx_treasury": execute_fx_treasury_task,
}


async def executor_node(state: WorkflowState) -> dict:
    """Execute the current step in the plan by dispatching to the appropriate agent.

    Looks up the agent function from the dispatch table, calls it with the
    step's task and conversation context, and records the result.

    Args:
        state: The current workflow state containing the plan and step index.

    Returns:
        A dictionary with updated agent outputs and step index.
    """
    if state.plan is None or state.current_step_index >= len(state.plan.steps):
        logger.warning("executor_no_steps_remaining")
        return {"error": "No steps remaining to execute."}

    current_step = state.plan.steps[state.current_step_index]
    agent_name = current_step.agent
    task = current_step.task

    logger.info(
        "executor_node_start",
        agent=agent_name,
        step_index=state.current_step_index,
        task=task[:100],
    )

    conversation_context = "\n".join(
        f"{message['role']}: {message['content']}" for message in state.conversation_history[-5:]
    )

    agent_function = AGENT_DISPATCH_TABLE.get(agent_name)
    if agent_function is None:
        error_message = f"Unknown agent: {agent_name}"
        logger.error("executor_unknown_agent", agent=agent_name)
        new_outputs = list(state.agent_outputs)
        new_outputs.append({"agent": agent_name, "result": error_message})
        return {
            "agent_outputs": new_outputs,
            "current_step_index": state.current_step_index + 1,
        }

    try:
        result = await agent_function(task=task, conversation_context=conversation_context)
    except Exception as error:
        logger.exception("executor_agent_failed", agent=agent_name)
        result = f"Agent {agent_name} failed: {error}"

    new_outputs = list(state.agent_outputs)
    new_outputs.append({"agent": agent_name, "result": result})

    logger.info(
        "executor_node_complete",
        agent=agent_name,
        step_index=state.current_step_index,
    )

    return {
        "agent_outputs": new_outputs,
        "current_step_index": state.current_step_index + 1,
    }
