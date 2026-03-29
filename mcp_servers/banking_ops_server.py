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
from mcp_servers.base import create_mock_mcp_app

MOCK_PORTFOLIO: dict[str, str | dict[str, str]] = {
    "customer_id": "C-011",
    "customer_name": "John Smith",
    "relationship_manager": "Emma Clarke",
    "total_aum": "USD 42,000,000",
    "net_worth": "USD 68,000,000",
    "risk_profile": "Growth",
    "asset_allocation": {
        "Public Equities": "48% (USD 20,160,000)",
        "Fixed Income": "20% (USD 8,400,000)",
        "Private Equity": "14% (USD 5,880,000)",
        "Hedge Funds": "8% (USD 3,360,000)",
        "Structured Products": "6% (USD 2,520,000)",
        "Real Asset Funds": "2% (USD 840,000)",
        "Cash within Portfolio": "2% (USD 840,000)",
    },
    "ytd_performance": "+8.4%",
    "one_year_return": "+16.7%",
    "benchmark_comparison": "+2.1% vs. MSCI World benchmark",
    "lombard_facility": "USD 10,000,000 limit / USD 3,200,000 drawn / USD 6,800,000 available @ 5.10% p.a.",
    "mortgage": "GBP 4,200,000 outstanding (One Hyde Park, London) @ 4.25% p.a.",
    "liquid_accounts": "USD 5,940,000 across GBP current, multi-currency, ISA, and liquidity accounts",
}

TOOL_DEFINITIONS = [
    {
        "name": "wealth_advisory",
        "description": "Wealth advisory operations for HNWI portfolio and investment queries",
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
        "name": "lending_credit",
        "description": "Lending and credit facility operations",
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
        "name": "banking_operation",
        "description": "General banking operations",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "context": {"type": "string"},
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
    system_prompt = params.get("system_prompt", "")

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
            search = TavilySearchResults(max_results=3)
            results = await asyncio.wait_for(search.ainvoke(task), timeout=5.0)
            return str(results)
        except Exception as e:
            print(f"Tavily search failed: {e}")
        return "No live market data retrieved."

    # Fetch RAG docs and live market data in parallel
    retrieved_docs, tavily_data = await asyncio.gather(_fetch_rag(), _fetch_tavily())

    # 3. Check for mock mode
    if settings.is_llm_mock_mode:
        portfolio = MOCK_PORTFOLIO
        return {
            "response": (
                f"[SMART MOCK ADVISORY]\n\n"
                f"Based on your AUM of {portfolio['total_aum']} and the query about '{task[:50]}', "
                f"I have consulted our recent market research and live market data.\n\n"
                f"RAG Context:\n{retrieved_docs[:200]}...\n\n"
                f"Tavily Context:\n{tavily_data[:200]}...\n\n"
                f"Our stance remains moderately constructive. Please contact your RM to discuss "
                f"how this outlook impacts your specific allocation."
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
        f"Client Account Summary:\nTotal AUM: {MOCK_PORTFOLIO['total_aum']}\n"
        f"Performance: {MOCK_PORTFOLIO['ytd_performance']}\n\n"
        f"Client Question: {task}\n\n"
        f"Conversation Context: {context}\n\n"
        f"Internal Research (RAG):\n{retrieved_docs}\n\n"
        f"Live Market Data (Tavily):\n{tavily_data}\n\n"
        f"Please provide a professional wealth advisory response."
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


def handle_lending_credit(params: dict) -> dict:
    """Generate a mock lending and credit response.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the mock response.
    """
    task = params.get("task", "")
    return {
        "response": (
            f"Lending Assessment for your inquiry: {task[:120]}\n\n"
            f"Based on your portfolio valuation of {MOCK_PORTFOLIO['total_aum']}, "
            f"the following credit facilities are available:\n\n"
            f"Lombard Credit Line:\n"
            f"  - Maximum facility: CHF 8,715,000 (70% LTV on diversified portfolio)\n"
            f"  - Indicative rate: SARON + 0.85% p.a.\n"
            f"  - Arrangement fee: 0.10% (waived for existing premium clients)\n"
            f"  - Flexible drawdown and repayment, no fixed maturity\n\n"
            f"Mortgage Financing:\n"
            f"  - Fixed 5-year: 1.35% p.a.\n"
            f"  - Fixed 10-year: 1.45% p.a.\n"
            f"  - Variable (SARON-linked): SARON + 0.65% p.a.\n"
            f"  - Maximum LTV: 80% (residential), 65% (commercial)\n\n"
            f"A detailed credit proposal can be prepared within 48 hours. "
            f"Please confirm if you would like to proceed."
        )
    }


def handle_banking_operation(params: dict) -> dict:
    """Generate a mock general banking response.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the mock response.
    """
    task = params.get("task", "")
    return {
        "response": (
            f"Banking operation processed for: {task[:120]}\n\n"
            f"The requested operation has been queued for processing. "
            f"Standard operations are completed within the same business day. "
            f"Cross-border transactions may require 1-2 additional business days."
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
