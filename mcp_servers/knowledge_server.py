"""Mock MCP server for Knowledge Systems (port 9002).

Serves: private_banking, compliance_tax, knowledge_query tools.

Run standalone:
    uv run uvicorn mocks.knowledge_server:app --host 0.0.0.0 --port 9002
"""

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from apps.api.config import resiliency_manager, settings
from mcp_servers.base import create_mock_mcp_app, get_persona_data

# Removed static MOCK_CLIENT and MOCK_ACCOUNTS - now using SQLite via get_persona_data

TOOL_DEFINITIONS = [
    {
        "name": "private_banking",
        "description": "Private banking operations for account management and transactions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "context": {"type": "string"},
                "username": {"type": "string"},
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
                "username": {"type": "string"},
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

    username = params.get("username", "jsmith")
    persona_data = get_persona_data(username) or {}
    profile = persona_data.get("profile", {})
    accounts = persona_data.get("accounts", [])
    credit = persona_data.get("credit", {})

    # 1. Mock Mode or Circuit Breaker Fallback
    if settings.is_llm_mock_mode or resiliency_manager.is_circuit_breaker_tripped:
        if "loan" in task.lower() or "lombard" in task.lower() or "credit" in task.lower():
            lombard_limit = credit.get("lombard_limit", 0)
            lombard_drawn = credit.get("lombard_drawn", 0)
            lombard_avail = lombard_limit - lombard_drawn
            return {
                "response": (
                    "[SMART SQLITE LOAN SUMMARY]\n\n"
                    "```json\n"
                    "{\n"
                    '  "type": "gauge",\n'
                    '  "title": "Lombard loans",\n'
                    '  "labels": ["Remaining lending value"],\n'
                    f'  "values": [{lombard_avail}, {lombard_limit}],\n'
                    '  "badge": "Sufficient"\n'
                    "}\n"
                    "```\n\n"
                    "| | |\n"
                    "|---|---|\n"
                    f"| Credit usage | **USD {lombard_drawn:,.0f}** |\n"
                    f"| Available credit | **USD {lombard_avail:,.0f}** |\n"
                ),
                "raw_data": {"profile": profile, "accounts": accounts, "credit": credit}
            }

        account_lines = "\n".join(
            f"  - {a['account_id']} ({a['account_type']}, {a['currency']}): {a['balance']:,.2f}"
            for a in accounts
        )
        total_aum = f"{profile.get('aum_usd', 0):,.0f}"
        return {
            "response": (
                f"[SMART SQLITE PRIVATE BANKING]\n\n"
                f"Client: {profile.get('full_name')} ({profile.get('customer_id')}) — {profile.get('risk_profile')} profile\n\n"
                f"Account Summary:\n{account_lines}\n"
                f"Total AUM (USD): {total_aum}\n\n"
                f"Regarding: {task[:120]}\n\n"
                f"The requested operation has been noted for your account."
            ),
            "raw_data": {"profile": profile, "accounts": accounts, "credit": credit}
        }

    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        max_retries=0,  # Fail fast!
    )

    prompt = (
        f"Client: {profile.get('full_name')} ({profile.get('customer_id')})\n"
        f"Risk Profile: {profile.get('risk_profile')}\n"
        f"AUM: USD {profile.get('aum_usd', 0):,.0f}\n"
        f"Account Data:\n{accounts}\n\n"
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
        # Define retry logic with exponential backoff
        retryer = AsyncRetrying(
            stop=stop_after_attempt(settings.llm_max_retries),
            wait=wait_exponential(
                multiplier=1, 
                min=settings.llm_retry_min_wait, 
                max=settings.llm_retry_max_wait
            ),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )

        async for attempt in retryer:
            with attempt:
                response = await llm.ainvoke(
                    [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=prompt),
                    ]
                )

        resiliency_manager.record_success()
        content = response.content
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        return {"response": str(content)}
    except Exception as e:
        resiliency_manager.record_failure(str(e))
        return {
            "response": f"Assistant service temporarily limited (429). Raw account data retrieved below.",
            "error": str(e),
            "raw_data": {
                "profile": profile,
                "accounts": accounts,
                "credit": credit
            }
        }


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

    if settings.is_llm_mock_mode or resiliency_manager.is_circuit_breaker_tripped:
        return {
            "response": (
                f"[SMART MOCK COMPLIANCE]\n\n"
                f"Regarding: {task[:120]}\n\n"
                f"Regulatory context: {retrieved_docs[:200]}...\n\n"
                f"You appear to be compliant. Contact tax specialists for details."
            ),
            "raw_data": {"retrieved_docs": retrieved_docs}
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
        # Define retry logic with exponential backoff
        retryer = AsyncRetrying(
            stop=stop_after_attempt(settings.llm_max_retries),
            wait=wait_exponential(
                multiplier=1, 
                min=settings.llm_retry_min_wait, 
                max=settings.llm_retry_max_wait
            ),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )

        async for attempt in retryer:
            with attempt:
                response = await llm.ainvoke(
                    [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=prompt),
                    ]
                )

        resiliency_manager.record_success()
        content = response.content
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        return {"response": str(content)}
    except Exception as e:
        resiliency_manager.record_failure(str(e))
        return {
            "response": f"Compliance service temporarily limited. Raw context retrieved.",
            "error": str(e),
            "raw_data": {"retrieved_docs": retrieved_docs}
        }


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

    if settings.is_llm_mock_mode or resiliency_manager.is_circuit_breaker_tripped:
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
                ),
                "raw_data": {"retrieved_docs": retrieved_docs}
            }

        return {
            "response": (
                f"[SMART MOCK KNOWLEDGE]\n\n"
                f"Result for: {task[:120]}\n\n"
                f"Policy context: {retrieved_docs[:200]}...\n\n"
                f"Refer to RM for the latest T&Cs."
            ),
            "raw_data": {"retrieved_docs": retrieved_docs}
        }

    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        max_retries=0,  # Fail fast!
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
        # Define retry logic with exponential backoff
        retryer = AsyncRetrying(
            stop=stop_after_attempt(settings.llm_max_retries),
            wait=wait_exponential(
                multiplier=1, 
                min=settings.llm_retry_min_wait, 
                max=settings.llm_retry_max_wait
            ),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )

        async for attempt in retryer:
            with attempt:
                response = await llm.ainvoke(
                    [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=prompt),
                    ]
                )

        resiliency_manager.record_success()
        content = response.content
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        return {"response": str(content)}
    except Exception as e:
        resiliency_manager.record_failure(str(e))
        return {
            "response": f"Knowledge service temporarily limited. Raw context retrieved.",
            "error": str(e),
            "raw_data": {"retrieved_docs": retrieved_docs}
        }


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
