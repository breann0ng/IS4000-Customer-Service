import asyncio
import uuid
import json
from apps.api.workflow.graph import workflow_graph
from apps.api.workflow.state import WorkflowState
from apps.api.config import settings

# Mock configuration for local run if needed
settings.gemini_api_key = "placeholder" # Should be picked up from .env if it exists

async def debug_stream():
    initial_state = WorkflowState(
        user_message="I'm looking to increase my exposure to JPY. What are the current indicative rates and can you suggest a staging strategy for a 5M USD conversion?",
        conversation_history=[],
        memory_context=[],
        session_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        username="john_smith",
    )
    
    print("Starting astream...")
    try:
        async for event in workflow_graph.astream(initial_state, stream_mode="updates"):
            print(f"\nEVENT: {list(event.keys())}")
            for node_name, node_output in event.items():
                print(f"NODE: {node_name}")
                # Try a simplified version of the route logic
                if isinstance(node_output, dict):
                    print(f"KEYS: {list(node_output.keys())}")
                else:
                    print(f"TYPE: {type(node_output)}")
    except Exception as e:
        print(f"\nCRASHED with: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_stream())
