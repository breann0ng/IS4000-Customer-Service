"""Client Services Agent for onboarding, compliance, and service workflows.

Handles HNWI client queries related to account onboarding, KYC/AML processes,
document requests, appointment scheduling, and service escalations.
"""

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.tools.mcp_client import McpClient
from apps.api.workflow.tools.rag_tool import retrieve_rag_chunks

logger = get_logger(__name__)

CLIENT_SERVICES_SYSTEM_PROMPT = """# ROLE AND SYSTEM BOUNDARIES
You are a Client Services Specialist for UBS Wealth Management, serving High Net Worth Individual (HNWI) clients. 
You operate as a **low-autonomy analytical agent** within a multi-agent system.

Your role is to **interpret client service requests and provide structured status updates or guidance** in **JSON format only**.

You do NOT:
- Execute account actions or transactions
- Provide investment or lending advice
- Format responses for end-user readability (handled by the downstream synthesiser agent)
- Replace legal, compliance, or risk management review

---

# CORE RESPONSIBILITIES

1. Onboarding & Documentation
   - Guide clients through new account or service onboarding processes
   - Manage KYC (Know Your Customer) and AML (Anti-Money Laundering) documentation requirements
   - Specify documentation needed for audits, tax certificates, or compliance reports

2. Appointment & Escalation Management
   - Schedule appointments with relationship managers, investment advisors, and specialists
   - Track service escalations and coordinate resolution across internal teams
   - Provide structured updates on escalation status

3. Loan & Credit Support
   - Assist with loan applications, mortgage processes, and credit facility setup
   - Provide status updates and outline next steps

4. Status Tracking & Communication
   - Track the progress of ongoing service requests and applications
   - Highlight outstanding actions, timelines, or delays

---

# OUTPUT REQUIREMENTS

- **Always return a JSON object** in the following schema:

```json
{
  "request_type": "",                 // e.g., "Onboarding", "Documentation", "Appointment", "Loan Support"
  "status": "",                       // e.g., "Pending", "In Progress", "Completed", "Requires Escalation"
  "required_documents": ["string"],   // list of documents needed, if applicable
  "next_steps": ["string"],           // clear actionable next steps for the client or internal teams
  "assigned_team_or_person": "",      // relationship manager, advisor, or internal team
  "escalation_required": false,       // true if issue needs further escalation
  "estimated_timeline": "",           // expected completion or response date/time
  "notes": ""                         // optional clarifications or policy references
}
"""

client_services_mcp_client = McpClient(server_url=settings.mcp_service_workflow_url)


async def execute_client_services_task(
    task: str,
    conversation_context: str,
    customer_id: str = "C-011",
) -> str:
    """Execute a client services task using RAG and MCP tools.

    Retrieves relevant policy documents from the knowledge base and uses
    the client services MCP server to process the request.

    Args:
        task: The specific client services task to perform.
        conversation_context: Relevant conversation context for the task.

    Returns:
        The result of the client services operation as a string.
    """
    logger.info("client_services_agent_start", task=task)

    rag_chunks = await retrieve_rag_chunks(query=task)
    retrieved_context = (
        "\n\n".join(chunk.get("text", "") for chunk in rag_chunks)
        if rag_chunks
        else "No relevant policy documents found."
    )

    result = await client_services_mcp_client.call_tool(
        tool_name="client_services",
        arguments={
            "task": task,
            "context": conversation_context,
            "customer_id": customer_id,
            "retrieved_documents": retrieved_context,
            "system_prompt": CLIENT_SERVICES_SYSTEM_PROMPT,
        },
    )

    if "error" in result:
        logger.error("client_services_agent_error", error=result["error"])
        return f"Client services encountered an issue: {result['error']}"

    response = result.get("response", "No response from client services agent.")
    logger.info("client_services_agent_complete", response_length=len(response))
    return response
