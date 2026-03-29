"""Mock MCP server for Knowledge Systems (port 9002).

Serves: private_banking, compliance_tax, knowledge_query tools.

Run standalone:
    uv run uvicorn mocks.knowledge_server:app --host 0.0.0.0 --port 9002
"""

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from apps.api.config import settings
from mcp_servers.base import create_mock_mcp_app

MOCK_ACCOUNTS = [
    {"account": "CH93 0076 2011 6238 5295 7", "currency": "CHF", "balance": "2,345,678.50"},
    {"account": "CH93 0076 2011 6238 5296 8", "currency": "EUR", "balance": "1,123,456.00"},
    {"account": "CH93 0076 2011 6238 5297 9", "currency": "USD", "balance": "3,456,789.25"},
    {"account": "CH93 0076 2011 6238 5298 0", "currency": "GBP", "balance": "567,890.75"},
]

TOOL_DEFINITIONS = [
    {
        "name": "private_banking",
        "description": "Private banking operations for account management and transactions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "context": {"type": "string"},
                "system_prompt": {"type": "string"},
            },
        },
    },
    {
        "name": "compliance_tax",
        "description": "Compliance and tax reporting operations",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "context": {"type": "string"},
                "retrieved_documents": {"type": "string"},
                "system_prompt": {"type": "string"},
            },
        },
    },
    {
        "name": "knowledge_query",
        "description": "Knowledge base query for policies and product information",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "context": {"type": "string"},
                "retrieved_documents": {"type": "string"},
                "system_prompt": {"type": "string"},
            },
        },
    },
]


async def handle_private_banking(params: dict) -> dict:
    """Generate a high-quality private banking response using LLM.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the generated response.
    """
    task = params.get("task", "")
    context = params.get("context", "")
    system_prompt = params.get("system_prompt", "")

    if settings.is_llm_mock_mode:
        if "loan" in task.lower() or "lombard" in task.lower() or "credit" in task.lower():
            return {
                "response": (
                    "[SMART MOCK LOAN SUMMARY]\n\n"
                    "```json\n"
                    "{\n"
                    '  "type": "gauge",\n'
                    '  "title": "Lombard loans",\n'
                    '  "labels": ["Remaining lending value"],\n'
                    '  "values": [61230, 80000],\n'
                    '  "badge": "Sufficient"\n'
                    "}\n"
                    "```\n\n"
                    "| | |\n"
                    "|---|---|\n"
                    "| Credit usage | **USD -179** |\n"
                    "| Available credit | **USD 61'230** |\n"
                )
            }

        account_lines = "\n".join(
            f"  - {account['account']} ({account['currency']}): {account['balance']}"
            for account in MOCK_ACCOUNTS
        )
        total_chf = "7,493,814.50"
        return {
            "response": (
                f"[SMART MOCK PRIVATE BANKING]\n\n"
                f"Account Summary:\n{account_lines}\n"
                f"Total (CHF equivalent): {total_chf}\n\n"
                f"Regarding: {task[:120]}\n\n"
                f"The requested operation has been noted for {MOCK_ACCOUNTS[0]['account']}."
            )
        }

    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
    )

    prompt = (
        f"Client Account Data:\n{MOCK_ACCOUNTS}\n\n"
        f"Task: {task}\n\n"
        f"Context: {context}\n\n"
        f"Provide a professional private banking summary or action confirmation."
    )
    if "loan" in task.lower() or "lombard" in task.lower() or "credit" in task.lower():
        prompt += (
            "\n\nIMPORTANT: For this loan request, include this exact JSON chart in your response:\n"
            "```json\n"
            "{\n"
            '  "type": "gauge",\n'
            '  "title": "Lombard loans",\n'
            '  "labels": ["Remaining lending value"],\n'
            '  "values": [61230, 80000],\n'
            '  "badge": "Sufficient"\n'
            "}\n"
            "```\n"
            "And output this exact markdown table below it:\n"
            "| | |\n"
            "|---|---|\n"
            "| Credit usage | **USD -179** |\n"
            "| Available credit | **USD 61'230** |\n"
        )

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt),
            ]
        )
        content = response.content
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        return {"response": str(content)}
    except Exception as e:
        return {"response": f"Private banking failed: {str(e)}", "error": str(e)}


async def handle_compliance_tax(params: dict) -> dict:
    """Generate a high-quality compliance and tax response using LLM and RAG.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the generated response.
    """
    task = params.get("task", "")
    context = params.get("context", "")
    system_prompt = params.get("system_prompt", "")

    # Retrieve context
    retrieved_docs = "No relevant regulatory context found."
    try:
        async with httpx.AsyncClient() as client:
            rag_response = await client.post(
                settings.mcp_rag_server_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "retrieve_documents",
                        "arguments": {"query": task, "top_k": 3},
                    },
                    "id": 1,
                },
                timeout=10.0,
            )
            if rag_response.status_code == 200:
                result = rag_response.json().get("result", {})
                chunks = result.get("chunks", [])
                if chunks:
                    retrieved_docs = "\n\n".join(f"[Regulatory Info]: {c['text']}" for c in chunks)
    except Exception:
        pass

    if settings.is_llm_mock_mode:
        return {
            "response": (
                f"[SMART MOCK COMPLIANCE]\n\n"
                f"Regarding: {task[:120]}\n\n"
                f"Regulatory context: {retrieved_docs[:200]}...\n\n"
                f"You appear to be compliant. Contact tax specialists for details."
            )
        }

    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
    )

    prompt = (
        f"Task: {task}\n\n"
        f"Regulatory Context from RAG:\n{retrieved_docs}\n\n"
        f"Provide a professional compliance and tax advisory response."
    )

    try:
        response = await llm.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=prompt)]
        )
        content = response.content
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        return {"response": str(content)}
    except Exception as e:
        return {"response": f"Compliance check failed: {str(e)}"}


async def handle_knowledge_query(params: dict) -> dict:
    """Generate a high-quality knowledge query response using LLM and RAG.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the generated response.
    """
    task = params.get("task", "")
    context = params.get("context", "")
    system_prompt = params.get("system_prompt", "")

    # Retrieve context
    retrieved_docs = "No relevant knowledge base entries found."
    try:
        async with httpx.AsyncClient() as client:
            rag_response = await client.post(
                settings.mcp_rag_server_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "retrieve_documents",
                        "arguments": {"query": task, "top_k": 3},
                    },
                    "id": 1,
                },
                timeout=10.0,
            )
            if rag_response.status_code == 200:
                result = rag_response.json().get("result", {})
                chunks = result.get("chunks", [])
                if chunks:
                    retrieved_docs = "\n\n".join(f"[Knowledge Base]: {c['text']}" for c in chunks)
    except Exception:
        pass

    if settings.is_llm_mock_mode:
        if "loan" in task.lower() or "lombard" in task.lower() or "credit" in task.lower():
            return {
                "response": (
                    "[SMART MOCK LOAN SUMMARY]\n\n"
                    "```json\n"
                    "{\n"
                    '  "type": "gauge",\n'
                    '  "title": "Lombard loans",\n'
                    '  "labels": ["Remaining lending value"],\n'
                    '  "values": [61230, 80000],\n'
                    '  "badge": "Sufficient"\n'
                    "}\n"
                    "```\n\n"
                    "| | |\n"
                    "|---|---|\n"
                    "| Credit usage | **USD -179** |\n"
                    "| Available credit | **USD 61'230** |\n"
                )
            }

        return {
            "response": (
                f"[SMART MOCK KNOWLEDGE]\n\n"
                f"Result for: {task[:120]}\n\n"
                f"Policy context: {retrieved_docs[:200]}...\n\n"
                f"Refer to RM for the latest T&Cs."
            )
        }

    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
    )

    prompt = (
        f"Query: {task}\n\n"
        f"Knowledge Base Context:\n{retrieved_docs}\n\n"
        f"Provide a professional response based on our available documents."
    )
    if "loan" in task.lower() or "lombard" in task.lower() or "credit" in task.lower():
        prompt += (
            "\n\nIMPORTANT: For this loan request, include this exact JSON chart in your response:\n"
            "```json\n"
            "{\n"
            '  "type": "gauge",\n'
            '  "title": "Lombard loans",\n'
            '  "labels": ["Remaining lending value"],\n'
            '  "values": [61230, 80000],\n'
            '  "badge": "Sufficient"\n'
            "}\n"
            "```\n"
            "And output this exact markdown table below it:\n"
            "| | |\n"
            "|---|---|\n"
            "| Credit usage | **USD -179** |\n"
            "| Available credit | **USD 61'230** |\n"
        )

    try:
        response = await llm.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=prompt)]
        )
        content = response.content
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        return {"response": str(content)}
    except Exception as e:
        return {"response": f"Knowledge query failed: {str(e)}"}


TOOL_HANDLERS = {
    "private_banking": handle_private_banking,
    "compliance_tax": handle_compliance_tax,
    "knowledge_query": handle_knowledge_query,
}

app = create_mock_mcp_app(
    title="Mock Knowledge MCP Server",
    tool_definitions=TOOL_DEFINITIONS,
    tool_handlers=TOOL_HANDLERS,
)
