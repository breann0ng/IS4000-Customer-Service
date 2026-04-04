import asyncio
import json

import httpx
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from apps.api.config import settings
from apps.api.customers.data_service import DataService
from apps.api.customers.registry import DEFAULT_CUSTOMER_ID
from apps.api.workflow.state import ComplianceTaxOutput, PrivateBankingOutput
from mcp_servers.base import create_mock_mcp_app

TOOL_DEFINITIONS = [
    {
        "name": "private_banking",
        "description": "Private banking operations for account management and transactions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "context": {"type": "string"},
                "customer_id": {"type": "string"},
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


async def _fetch_tavily(task: str) -> str:
    """Fetch live market or regulatory data using Tavily API."""
    if settings.is_llm_mock_mode or not settings.tavily_api_key:
        return "No live market data retrieved."
    try:
        search = TavilySearchResults(max_results=3)
        results = await asyncio.wait_for(search.ainvoke(task), timeout=5.0)
        return str(results)
    except Exception as e:
        print(f"Tavily search failed: {e}")
    return "No live market data retrieved."


async def handle_private_banking(params: dict) -> dict:
    """Generate a high-quality private banking response using dynamic data and LLM.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the generated response.
    """
    task = params.get("task", "")
    context = params.get("context", "")
    customer_id = params.get("customer_id", DEFAULT_CUSTOMER_ID)
    system_prompt = params.get("system_prompt", "")

    client_profile, accounts = DataService.get_banking_context(customer_id)
    lending_context = DataService.get_lending_context(customer_id)
    planning_context = DataService.get_financial_planning(customer_id)

    # Fetch live market data if relevant (e.g., mortgage rates, market conditions)
    market_info = ""
    is_loan_query = any(word in task.lower() for word in ["loan", "lombard", "credit", "mortgage"])
    if is_loan_query:
        market_info = await _fetch_tavily(
            f"Current mortgage and Lombard lending rates and trends for: {task}"
        )

    if settings.is_llm_mock_mode:
        if "performance" in task.lower() or "return" in task.lower():
            return {
                "response": (
                    f"[DYNAMIC MOCK PERFORMANCE]\n\n"
                    f"Your YTD Return is **{client_profile.get('ytd_return_pct')}%**. "
                    f"Your 1-year return is **{client_profile.get('one_year_return_pct')}%**.\n\n"
                    f"As a client with "
                    f"**{client_profile.get('derived_flags', {}).get('cross_border_exposure')}** "
                    "cross-border exposure, "
                    f"we recommend a review of these returns against your "
                    f"**{client_profile.get('risk_profile')}** risk profile."
                )
            }

        if is_loan_query:
            # Extract raw values for the gauge if possible
            limit = 15000000  # Specific to John Smith C-001
            drawn = 4200000

            return {
                "response": (
                    f"[DYNAMIC MOCK LOAN SUMMARY]\n\n"
                    f"Based on your AUM of {lending_context.get('total_aum', 'N/A')}, "
                    "here is your current credit status:\n\n"
                    "```json\n"
                    "{\n"
                    '  "type": "gauge",\n'
                    '  "title": "Lombard loans",\n'
                    '  "labels": ["Remaining lending value"],\n'
                    f'  "values": [{limit - drawn}, {limit}],\n'
                    '  "badge": "Sufficient"\n'
                    "}\n"
                    "```\n\n"
                    "| | |\n"
                    "|---|---|\n"
                    f"| Credit usage | **SGD {drawn:,}** |\n"
                    f"| Available credit | **SGD {limit - drawn:,}** |\n"
                    f"\nMarket Context:\n{market_info[:200]}..."
                )
            }

        account_lines = "\n".join(
            f"  - {account['account_id']} ({account['type']}, {account['currency']}): "
            f"{account['balance']}"
            for account in accounts
        )
        total_sgd = str(client_profile.get("aum_sgd", 0))
        return {
            "response": (
                f"[DYNAMIC MOCK PRIVATE BANKING]\n\n"
                f"Client: {client_profile.get('name', 'Unknown')} "
                f"({client_profile.get('customer_id', customer_id)}) — "
                f"{client_profile.get('risk_profile', 'Unknown')} profile\n\n"
                f"Account Summary:\n{account_lines}\n"
                f"Total (SGD equivalent): {total_sgd}\n\n"
                f"Derived Flags: {client_profile.get('derived_flags')}\n"
                f"Preferences: {client_profile.get('preferences')}\n\n"
                f"Regarding: {task[:120]}\n\n"
                "The requested operation has been noted for your account."
            )
        }

    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
    )
    structured_llm = llm.with_structured_output(PrivateBankingOutput)

    prompt = (
        f"Client: {client_profile.get('name')} ({client_profile.get('customer_id')})\n"
        f"Risk Profile: {client_profile.get('risk_profile')}\n"
        f"Performance: YTD {client_profile.get('ytd_return_pct')}%, "
        f"1Y {client_profile.get('one_year_return_pct')}%\n"
        f"AUM: SGD {client_profile.get('aum_sgd', 0):,}\n"
        f"Account Data:\n{accounts}\n\n"
        f"Preferences & Goals:\n{planning_context}\n\n"
        f"Lending Context:\n{lending_context}\n\n"
        f"Market Information (Live):\n{market_info}\n\n"
        f"Task: {task}\n\n"
        f"Context: {context}\n\n"
        "Provide a professional private banking summary or action confirmation. "
        "Default all currency reporting to SGD.\n"
        "CRITICAL — DATA ACCURACY: You MUST use the EXACT numerical values provided above "
        "for AUM, account balances, YTD return, and all financial figures. "
        "NEVER estimate, round differently, "
        "or generate your own figures. Every number in your response must be directly traceable "
        "to the client data above."
    )

    if is_loan_query:
        prompt += (
            "\n\nIMPORTANT: For this loan request, include the available vs total limit "
            "from the Lending Context provided in the data field."
        )

    # Verified financial data from the database
    verified_aum = client_profile.get("aum_sgd", 0)
    verified_ytd = client_profile.get("ytd_return_pct")

    try:
        result = await structured_llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt),
            ]
        )

        # Overwrite financial figures with verified DB values on the Pydantic model
        if not isinstance(result, PrivateBankingOutput):
            return {"response": json.dumps(result) if isinstance(result, dict) else str(result)}
        data = result.data
        for key in ("aum", "aum_sgd", "total_aum", "total_value_sgd", "portfolio_value"):
            if key in data:
                data[key] = verified_aum
        for key in ("ytd_return_pct", "ytd_performance_pct", "ytd_return"):
            if key in data and verified_ytd is not None:
                data[key] = verified_ytd

        return {"response": result.model_dump_json()}
    except Exception as e:
        return {"response": f"Private banking failed: {str(e)}", "error": str(e)}


async def handle_compliance_tax(params: dict) -> dict:
    """Generate a high-quality compliance and tax response using LLM and RAG/Live search.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the generated response.
    """
    task = params.get("task", "")
    customer_id = params.get("customer_id", DEFAULT_CUSTOMER_ID)
    system_prompt = params.get("system_prompt", "")

    compliance_data = DataService.get_compliance_context(customer_id)

    # Retrieve RAG context
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
    except Exception:  # noqa: S110
        pass

    # Fetch live market/regulatory data
    live_info = await _fetch_tavily(f"Current regulations and tax updates for: {task}")

    if settings.is_llm_mock_mode:
        return {
            "response": (
                f"[DYNAMIC MOCK COMPLIANCE]\n\n"
                f"Tax Profile: {compliance_data.get('tax_profile')}\n\n"
                f"KYC Status: {compliance_data.get('kyc_status')} "
                f"(Last reviewed: {compliance_data.get('kyc_last_reviewed')})\n"
                f"Triggers: {compliance_data.get('system_triggers')}\n\n"
                f"Regarding: {task[:120]}\n\n"
                f"Regulatory context (Internal): {retrieved_docs[:200]}...\n\n"
                f"Live Market Info: {live_info[:200]}...\n\n"
                "You appear to be compliant based on available info. "
                "Contact tax specialists for details."
            )
        }

    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
    )
    structured_llm = llm.with_structured_output(ComplianceTaxOutput)

    prompt = (
        f"Task: {task}\n\n"
        f"Client Compliance Data:\n{compliance_data}\n\n"
        f"Internal Regulatory Context (RAG):\n{retrieved_docs}\n\n"
        f"Live Tax/Regulatory Updates (Tavily):\n{live_info}\n\n"
        f"Provide a professional compliance and tax advisory response.\n"
        "CRITICAL — DATA ACCURACY: You MUST use the EXACT numerical values from the "
        "Client Compliance Data above. "
        "NEVER fabricate or estimate financial figures. Every number must be directly traceable "
        "to the provided data."
    )

    try:
        result = await structured_llm.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=prompt)]
        )
        if isinstance(result, BaseModel):
            return {"response": result.model_dump_json()}
        return {"response": json.dumps(result)}
    except Exception as e:
        return {"response": f"Compliance check failed: {str(e)}"}


async def handle_knowledge_query(params: dict) -> dict:
    """Generate a high-quality knowledge query response using LLM, RAG, and Live Search.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the generated response.
    """
    task = params.get("task", "")
    system_prompt = params.get("system_prompt", "")

    # Retrieve RAG context
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
    except Exception:  # noqa: S110
        pass

    # Fetch live information
    live_info = await _fetch_tavily(f"Current market info and news for: {task}")

    if settings.is_llm_mock_mode:
        return {
            "response": (
                f"[DYNAMIC MOCK KNOWLEDGE]\n\n"
                f"Result for: {task[:120]}\n\n"
                f"Policy context: {retrieved_docs[:200]}...\n\n"
                f"Live Market Context: {live_info[:200]}...\n\n"
                f"Refer to RM for the latest T&Cs."
            )
        }

    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
    )

    prompt = (
        f"Query: {task}\n\n"
        f"Internal Knowledge Base Context:\n{retrieved_docs}\n\n"
        f"Live Market Environment (Tavily):\n{live_info}\n\n"
        "Provide a professional response based on our available documents "
        "and current market context."
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
