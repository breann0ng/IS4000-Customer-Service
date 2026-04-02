"""Executor node for the LangGraph workflow.

Dispatches planned steps to the appropriate specialist agents and
collects their results for UBS Wealth Management HNWI support.
"""

import asyncio

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


async def _run_step(agent_name: str, task: str, conversation_context: str, username: str) -> dict:
    """Run a single agent step, returning a result dict."""
    agent_function = AGENT_DISPATCH_TABLE.get(agent_name)
    if agent_function is None:
        logger.error("executor_unknown_agent", agent=agent_name)
        return {"agent": agent_name, "result": f"Unknown agent: {agent_name}"}
    try:
        result = await agent_function(task=task, conversation_context=conversation_context, username=username)
        return {"agent": agent_name, "result": result}
    except Exception as error:
        logger.exception("executor_agent_failed", agent=agent_name)
        return {"agent": agent_name, "result": f"Agent {agent_name} failed: {error}"}


async def executor_node(state: WorkflowState) -> dict:
    """Execute ALL remaining planned steps in parallel using asyncio.gather().

    Runs every not-yet-completed step concurrently so multi-agent plans
    complete in the time of the slowest agent rather than their sum.

    Args:
        state: The current workflow state containing the plan and step index.

    Returns:
        A dictionary with all agent outputs and the step index advanced past all steps.
    """
    if state.plan is None or state.current_step_index >= len(state.plan.steps):
        logger.warning("executor_no_steps_remaining")
        return {"error": "No steps remaining to execute."}

    # Collect all remaining (not yet completed) steps
    remaining_steps = [
        (step, idx)
        for idx, step in enumerate(state.plan.steps)
        if not step.completed and idx >= state.current_step_index
    ]

    if not remaining_steps:
        return {"current_step_index": len(state.plan.steps)}

    conversation_context = "\n".join(
        f"{message['role']}: {message['content']}" for message in state.conversation_history[-5:]
    )

    logger.info(
        "executor_node_parallel_start",
        step_count=len(remaining_steps),
        agents=[step.agent for step, _ in remaining_steps],
    )

    # Run all steps concurrently
    tasks = [
        _run_step(step.agent, step.task, conversation_context, state.username) 
        for step, _ in remaining_steps
    ]
    results = await asyncio.gather(*tasks)

    new_outputs = list(state.agent_outputs) + list(results)

    # Mark all steps complete in the plan copy
    new_plan = state.plan.model_copy(deep=True)
    for (step, idx), result in zip(remaining_steps, results):
        new_plan.steps[idx].completed = True
        new_plan.steps[idx].result = result["result"]

    logger.info("executor_node_parallel_complete", step_count=len(results))

    return {
        "agent_outputs": new_outputs,
        "current_step_index": len(state.plan.steps),  # Skip straight to synthesizer
        "plan": new_plan,
    }
