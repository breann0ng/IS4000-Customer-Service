import asyncio
import uuid
import json
from apps.api.workflow.graph import workflow_graph
from apps.api.workflow.state import WorkflowState
from apps.api.config import settings

# Mock _serialize_for_json
def _serialize_for_json(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return str(obj)

# Mock _sse
def _sse(event, data):
    print(f"\n[EVENT: {event}]\nDATA: {json.dumps(data, indent=2, default=str)}")
    return ""

async def debug_stream_full():
    initial_state = WorkflowState(
        user_message="I'm looking to increase my exposure to JPY. What are the current indicative rates and can you suggest a staging strategy for a 5M USD conversion?",
        conversation_history=[],
        memory_context=[],
        session_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        username="john_smith",
    )
    
    print("Starting simulated event_generator...")
    try:
        async for event in workflow_graph.astream(initial_state, stream_mode="updates"):
            for node_name, node_output in event.items():
                print(f"DEBUG: Processing node {node_name}")
                if node_name == "planner":
                    plan = node_output.get("plan") if isinstance(node_output, dict) else getattr(node_output, "plan", None)
                    if plan:
                        print("SUCCESS: Plan found")
                        steps = [{"agent": step.agent, "task": step.task} for step in getattr(plan, "steps", [])]
                        _sse("planning", {"reasoning": getattr(plan, "reasoning", ""), "steps": steps})

                elif node_name == "executor":
                    outputs = node_output.get("agent_outputs") if isinstance(node_output, dict) else getattr(node_output, "agent_outputs", [])
                    if outputs:
                        latest = outputs[-1]
                        print(f"SUCCESS: Agent Step - {latest.get('agent')}")
                        _sse("agent_step", {"agent": latest.get("agent", "Specialist"), "result": str(latest.get("result"))})

                elif node_name == "synthesizer":
                    final_res = node_output.get("final_response") if isinstance(node_output, dict) else getattr(node_output, "final_response", None)
                    if final_res:
                        print("SUCCESS: Synthesis found")
                        _sse("synthesizing", {"status": "Complete"})

    except Exception as e:
        print(f"\nCRASHED with: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_stream_full())
