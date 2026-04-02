"""Mock MCP server for Banking Operations (port 9001).

Serves: wealth_advisory, lending_credit, banking_operation tools.

Run standalone:
    uv run uvicorn mocks.banking_ops_server:app --host 0.0.0.0 --port 9001
"""

import asyncio

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools.tavily_search import TavilySearchResults
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from apps.api.config import resiliency_manager, settings
from mcp_servers.base import create_mock_mcp_app, get_persona_data

# Removed static MOCK_PORTFOLIO - now using SQLite via get_persona_data

TOOL_DEFINITIONS = [
    {
        "name": "wealth_advisory",
        "description": "Wealth advisory operations for HNWI portfolio and investment queries",
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
        "name": "lending_credit",
        "description": "Lending and credit facility operations",
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
        "name": "banking_operation",
        "description": "General banking operations",
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

    persona_data = get_persona_data(username) or {}
    profile = persona_data.get("profile", {})
    portfolio = persona_data.get("portfolio", {})
    real_estate = persona_data.get("real_estate", [])
    
    aum_str = f"USD {profile.get('aum_usd', 0):,.0f}"
    perf_str = f"{portfolio.get('ytd_return_pct', 0):+.1f}%"
    
    # Format real estate details for the prompt
    re_summary = "No real estate records found."
    if real_estate:
        re_summary = "\n".join([f"- {re.get('property')} in {re.get('location')}: USD {re.get('value_local', 0):,.0f}" for re in real_estate])

    # 3. Check for mock mode or circuit breaker
    if settings.is_llm_mock_mode or resiliency_manager.is_circuit_breaker_tripped:
        return {
            "agent_name": "wealth_advisory",
            "response": f"Strategic wealth advisory assessment generated for: {task[:60]}...",
            "status": "COMPLETED",
            "next_steps": [
                "Schedule a detailed portfolio review with your RM",
                "Review the suggested asset allocation adjustments"
            ],
            "metrics": [
                {"label": "AUM", "value": aum_str},
                {"label": "YTD Return", "value": perf_str, "trend": "up" if "+" in perf_str else "down"}
            ],
            "requires_escalation": False,
            "raw_data": {
                "profile": profile,
                "portfolio": portfolio,
                "market_data_preview": tavily_data[:200],
                "research_preview": retrieved_docs[:200]
            }
        }


    # 4. Call Gemini for real synthesis
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.2,
        max_output_tokens=1500,
        max_retries=0,  # Fail fast!
    )

    prompt = (
        f"Client Account Summary:\nTotal AUM: {aum_str}\n"
        f"Performance: {perf_str}\n\n"
        f"Real Estate Portfolio:\n{re_summary}\n\n"
        f"Client Question: {task}\n\n"
        f"Conversation Context: {context}\n\n"
        f"Internal Research (RAG):\n{retrieved_docs}\n\n"
        f"Live Market Data (Tavily):\n{tavily_data}\n\n"
        f"Please provide a professional wealth advisory response."
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
        
        # Note: In a real implementation, we would use with_structured_output(SpecialistAgentOutput)
        # here. For now, we wrap the LLM response in the expected structure.
        return {
            "agent_name": "wealth_advisory",
            "response": str(content),
            "status": "COMPLETED",
            "next_steps": ["Discuss these insights with your advisor"],
            "metrics": [
                {"label": "AUM", "value": aum_str},
                {"label": "YTD Return", "value": perf_str}
            ],
            "requires_escalation": False,
            "raw_data": {
                "aum": aum_str,
                "ytd_return": perf_str
            }
        }
    except Exception as e:
        resiliency_manager.record_failure(str(e))
        return {
            "agent_name": "wealth_advisory",
            "response": f"Advisory service temporarily limited (LLM Error).",
            "status": "ERROR",
            "next_steps": ["Retry in 60 seconds"],
            "metrics": [],
            "requires_escalation": True,
            "raw_data": {
                "error": str(e),
                "aum": aum_str,
                "ytd_return": perf_str
            }
        }



def handle_lending_credit(params: dict) -> dict:
    """Generate a mock lending and credit response.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the mock response.
    """
    task = params.get("task", "")
    username = params.get("username", "jsmith")
    persona_data = get_persona_data(username) or {}
    credit = persona_data.get("credit", {})
    profile = persona_data.get("profile", {})
    real_estate = persona_data.get("real_estate", [])
    
    aum_str = f"USD {profile.get('aum_usd', 0):,.0f}"
    lombard_limit = credit.get("lombard_limit", 0)
    mortgage_sgd = credit.get("mortgage_outstanding", 0)

    return {
        "agent_name": "lending_credit",
        "response": f"Lending and credit facility assessment for: {task[:60]}...",
        "status": "COMPLETED",
        "next_steps": [
            "Confirm interest in the SARON-indexed Lombard facility",
            "Provide updated property valuation for mortgage refinancing"
        ],
        "metrics": [
            {"label": "Lombard Limit", "value": f"USD {lombard_limit:,.0f}"},
            {"label": "Mortgage", "value": f"SGD {mortgage_sgd:,.0f}"}
        ],
        "requires_escalation": False,
        "raw_data": {
            "aum": aum_str,
            "credit_facilities": {
                "lombard": {
                    "limit": lombard_limit,
                    "rate": "SARON + 0.85%"
                },
                "mortgage": {
                    "outstanding": mortgage_sgd,
                    "rate": "1.35% fixed"
                }
            },
            "real_estate": real_estate
        }
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
        "agent_name": "banking_operation",
        "response": f"Banking operation request for {task[:60]}... has been queued.",
        "status": "IN_PROGRESS",
        "next_steps": [
            "Await same business day completion for standard requests",
            "Cross-border verification may take 1-2 additional days"
        ],
        "metrics": [],
        "requires_escalation": False,
        "raw_data": {
            "operation": task[:120],
            "processing_priority": "standard"
        }
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
