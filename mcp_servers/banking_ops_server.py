"""Mock MCP server for Banking Operations (port 9001).

Serves: wealth_advisory, lending_credit, banking_operation tools.

Run standalone:
    uv run uvicorn mocks.banking_ops_server:app --host 0.0.0.0 --port 9001
"""

import asyncio

import httpx
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from apps.api.config import settings
from apps.api.customers.data_service import DataService
from mcp_servers.base import create_mock_mcp_app

TOOL_DEFINITIONS = [
    {
        "name": "wealth_advisory",
        "description": "Wealth advisory operations for HNWI portfolio and investment queries",
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
        "name": "lending_credit",
        "description": "Lending and credit facility operations",
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
        "name": "banking_operation",
        "description": "General banking operations",
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
]


async def handle_wealth_advisory(params: dict) -> dict:
    """Generate a high-quality wealth advisory response using LLM and RAG context.

    Queries the RAG server for relevant document chunks before using Gemini
    to synthesize a professional, data-backed response.

    Args:
        params: Tool invocation arguments including 'task' and 'context'.

    Returns:
        A dictionary with the generated advisor response.
    """
    task = params.get("task", "")
    context = params.get("context", "")
    customer_id = params.get("customer_id", "C-011")
    system_prompt = params.get("system_prompt", "")

    portfolio = DataService.get_advisory_context(customer_id)
    planning = DataService.get_financial_planning(customer_id)
    risk = DataService.get_risk_analysis(customer_id)

    async def _fetch_rag() -> str:
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
                    timeout=4.0,
                )
                if rag_response.status_code == 200:
                    result = rag_response.json().get("result", {})
                    chunks = result.get("chunks", [])
                    if chunks:
                        return "\n\n".join(
                            f"[Source: {c['metadata']['source']}]\n{c['text']}" for c in chunks
                        )
        except Exception as e:
            print(f"RAG retrieval failed: {e}")
        return "No relevant market research found."

    async def _fetch_tavily() -> str:
        if settings.is_llm_mock_mode or not settings.tavily_api_key:
            return "No live market data retrieved."
        try:
            # Construct a better search query to ensure relevant market context is found
            search_query = f"Current global market outlook, trends, and macroeconomic and sector news relevant to: {task}"
            search = TavilySearchResults(max_results=5)
            results = await asyncio.wait_for(search.ainvoke(search_query), timeout=6.0)
            
            if isinstance(results, list):
                return "\n\n".join(
                    f"[Source: {r.get('url', 'N/A')}]\n{r.get('content', r.get('text', str(r)))}"
                    for r in results
                )
            return str(results)
        except Exception as e:
            print(f"Tavily search failed: {e}")
        return "No live market data retrieved."

    # Fetch RAG docs and live market data in parallel
    retrieved_docs, tavily_data = await asyncio.gather(_fetch_rag(), _fetch_tavily())

    # 3. Check for mock mode
    if settings.is_llm_mock_mode:
        return {
            "response": (
                f"[SMART MOCK ADVISORY]\n\n"
                f"Client: {portfolio.get('customer_name', 'Unknown')}\n"
                f"AUM: {portfolio.get('total_aum', 'N/A')}\n"
                f"Performance: {portfolio.get('ytd_performance')} (Attribution: {portfolio.get('performance_attribution')})\n"
                f"Risk Metrics: {portfolio.get('risk_metrics')}\n"
                f"Strategic Goals: {planning.get('goals')}\n\n"
                f"Live Market Intelligence (Tavily):\n{tavily_data[:500]}...\n\n"
                f"Based on your query about '{task[:50]}', our stance remains moderately constructive. "
                f"Please contact your RM to discuss how this outlook impacts your specific allocation."
            )
        }

    # 4. Call Gemini for real synthesis
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.2,
        max_output_tokens=1500,
    )

    prompt = (
        f"Client Account Summary:\nTotal AUM: {portfolio.get('total_aum')}\n"
        f"Performance: {portfolio.get('ytd_performance')}\n"
        f"Attribution: {portfolio.get('performance_attribution')}\n"
        f"Risk Metrics: {portfolio.get('risk_metrics')}\n"
        f"Financial Goals: {planning.get('goals')}\n"
        f"Asset Allocation:\n{portfolio.get('asset_allocation')}\n\n"
        f"Client Question: {task}\n\n"
        f"Conversation Context: {context}\n\n"
        f"Internal Research (RAG):\n{retrieved_docs}\n\n"
        f"Live Market Data (Tavily):\n{tavily_data}\n\n"
        f"Please provide a professional wealth advisory response in JSON format. \n"
        f"IMPORTANT: Proactively include specific, quantitative market insights (index levels, rate changes) "
        f"from the Tavily data in your 'market_context' field. Do not be vague or generic. "
        f"Default all currency reporting to SGD unless the user explicitly requests another currency."
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
        return {"response": f"Wealth advisory processing failed: {str(e)}", "error": str(e)}


async def handle_lending_credit(params: dict) -> dict:
    """Generate a high-quality lending and credit response using dynamic data and live search.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the response.
    """
    task = params.get("task", "")
    customer_id = params.get("customer_id", "C-011")
    lending = DataService.get_lending_context(customer_id)
    planning = DataService.get_financial_planning(customer_id)

    # Fetch live mortgage or lending rates/products
    market_info = await asyncio.to_thread(_fetch_tavily_sync, f"Current mortgage and Lombard lending rates and products for: {task}")

    return {
        "response": (
            f"Lending Assessment for your inquiry: {task[:120]}\n\n"
            f"Based on your portfolio valuation of {lending.get('total_aum')} and YTD return of {lending.get('ytd_return')}, "
            f"the following credit facilities are currently associated with your account:\n\n"
            f"Current Facilities:\n"
            f"  - Lombard: {lending.get('lombard_facility')}\n"
            f"  - Mortgage: {lending.get('mortgage')}\n\n"
            f"Financial Goals (Relevant to Lending): {planning.get('goals')}\n\n"
            f"Market Intelligence (Live Search):\n{market_info[:500]}...\n\n"
            f"New Facility Options & Guidelines:\n"
            f"  - Indicative LTV: Based on live market collateral valuation\n"
            f"  - Indicative Rate: Derived from live benchmark rates (e.g. SARON/LIBOR) as shown above\n"
            f"  - Arrangement fee: Standard 0.10% (waived for existing premium clients)\n\n"
            f"A detailed credit proposal can be prepared within 48 hours. "
            f"Please confirm if you would like to proceed with a formal application."
        )
    }

def _fetch_tavily_sync(task: str) -> str:
    """Synchronous wrapper for tavily search."""
    if settings.is_llm_mock_mode or not settings.tavily_api_key:
        return "No live market data retrieved."
    try:
        from langchain_community.tools.tavily_search import TavilySearchResults
        search = TavilySearchResults(max_results=3)
        return str(search.invoke(task))
    except Exception as e:
        print(f"Tavily search failed: {e}")
    return "No live market data retrieved."


async def handle_banking_operation(params: dict) -> dict:
    """Generate a mock general banking response with live operational context.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the response.
    """
    task = params.get("task", "")
    
    # Fetch live information on banking procedures or news if relevant
    live_ops_info = await _fetch_tavily(f"Banking operations procedures or holiday schedules for: {task}")

    return {
        "response": (
            f"Banking operation processed for: {task[:120]}\n\n"
            f"Operational Context (Live Search):\n{live_ops_info[:300]}...\n\n"
            f"The requested operation has been queued for processing. "
            f"Standard operations are completed within the same business day. "
            f"Cross-border transactions may require 1-2 additional business days depending on receiving institution."
        )
    }


TOOL_HANDLERS = {
    "wealth_advisory": handle_wealth_advisory,
    "lending_credit": handle_lending_credit,
    "banking_operation": handle_banking_operation,
}

app = create_mock_mcp_app(
    title="Mock Banking Ops MCP Server",
    tool_definitions=TOOL_DEFINITIONS,
    tool_handlers=TOOL_HANDLERS,
)
