"""
Search provider adapter for Z-TRUST.

Provides pluggable retrieval adapters:
1. GroqBrowserSearchAdapter — Uses Groq's official server-side `browser_search` tool
   on supported models (openai/gpt-oss-120b, openai/gpt-oss-20b).
2. TavilySearchAdapter — Documented REST API via https://api.tavily.com/search (TAVILY_API_KEY).
3. SerperSearchAdapter — Documented REST API via https://google.serper.dev/search (SERPER_API_KEY).
4. DuckDuckGoSearchAdapter — Reliable zero-key web search fallback via httpx.

No search results are ever fabricated. If retrieval fails, clear errors are returned.
"""

import logging
import os
import re
import urllib.parse
from html import unescape
from typing import Optional

import httpx

logger = logging.getLogger("z-trust.search")


# ---------------------------------------------------------------------------
# 1. Groq Browser Search Adapter
# ---------------------------------------------------------------------------

def search_groq_browser(
    client,
    query: str,
    search_model: str = "openai/gpt-oss-120b",
    timeout: int = 30,
) -> dict:
    """Execute search using Groq's official built-in browser_search tool."""
    result = {
        "sources": [],
        "raw_content": "",
        "search_executed": False,
        "provider": "groq_browser_search",
        "error": None,
    }

    try:
        response = client.chat.completions.create(
            model=search_model,
            messages=[
                {
                    "role": "user",
                    "content": f"Search the web to find factual evidence and sources for: {query}",
                }
            ],
            tools=[{"type": "browser_search"}],
            tool_choice="required",
            timeout=timeout,
        )

        message = response.choices[0].message
        result["raw_content"] = message.content or ""

        executed_tools = getattr(message, "executed_tools", None)
        if executed_tools:
            result["search_executed"] = True
            for tool in executed_tools:
                # Handle search_results attribute
                sr = getattr(tool, "search_results", None)
                if isinstance(tool, dict):
                    sr = tool.get("search_results") or tool.get("output", {}).get("results")

                if sr:
                    results_list = []
                    if hasattr(sr, "results"):
                        results_list = sr.results
                    elif isinstance(sr, list):
                        results_list = sr
                    elif isinstance(sr, dict) and "results" in sr:
                        results_list = sr["results"]

                    for item in results_list:
                        title = getattr(item, "title", "") if not isinstance(item, dict) else item.get("title", "")
                        url = getattr(item, "url", "") if not isinstance(item, dict) else item.get("url", "")
                        snippet = getattr(item, "content", "") if not isinstance(item, dict) else item.get("snippet", "")
                        if title or url:
                            result["sources"].append({
                                "title": title or "Source",
                                "url": url or "",
                                "snippet": snippet or "",
                            })

                # If snippets were not in search_results, check tool output string
                tool_output = getattr(tool, "output", "") if not isinstance(tool, dict) else tool.get("output", "")
                if isinstance(tool_output, str) and tool_output and not result["sources"]:
                    # Extract URLs from output text if needed
                    urls = re.findall(r"https?://[^\s\)]+", tool_output)
                    for u in urls[:5]:
                        result["sources"].append({
                            "title": "Web Reference",
                            "url": u,
                            "snippet": tool_output[:300],
                        })

    except Exception as e:
        error_name = type(e).__name__
        err_str = str(e)
        if "404" in err_str or "NotFoundError" in error_name:
            result["error"] = f"Groq search model '{search_model}' not found or not accessible on this account."
        elif "429" in err_str or "RateLimitError" in error_name:
            result["error"] = "Groq API daily token rate limit exceeded for search model."
        elif "Timeout" in error_name or "timed out" in err_str.lower():
            result["error"] = "Groq browser search timed out."
        elif "400" in err_str or "BadRequestError" in error_name:
            result["error"] = f"Groq model '{search_model}' does not support browser_search tool."
        else:
            result["error"] = f"Groq browser search failed: {error_name}"

    return result


# ---------------------------------------------------------------------------
# 2. Tavily Search Adapter (Documented API: https://api.tavily.com/search)
# ---------------------------------------------------------------------------

def search_tavily(query: str, api_key: str, max_results: int = 5, timeout: int = 15) -> dict:
    """Execute search using official Tavily Search REST API."""
    result = {
        "sources": [],
        "raw_content": "",
        "search_executed": False,
        "provider": "tavily",
        "error": None,
    }

    if not api_key:
        result["error"] = "TAVILY_API_KEY is not configured."
        return result

    try:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
                "include_answer": True,
            },
            timeout=timeout,
        )

        if resp.status_code == 200:
            data = resp.json()
            result["search_executed"] = True
            result["raw_content"] = data.get("answer", "")
            for item in data.get("results", []):
                result["sources"].append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                })
        elif resp.status_code == 401:
            result["error"] = "Tavily API key is invalid."
        elif resp.status_code == 429:
            result["error"] = "Tavily rate limit exceeded."
        else:
            result["error"] = f"Tavily search returned HTTP {resp.status_code}."
    except Exception as e:
        result["error"] = f"Tavily search failed: {type(e).__name__}"

    return result


# ---------------------------------------------------------------------------
# 3. Serper Google Search Adapter (Documented API: https://google.serper.dev/search)
# ---------------------------------------------------------------------------

def search_serper(query: str, api_key: str, max_results: int = 5, timeout: int = 15) -> dict:
    """Execute search using official Serper Google Search REST API."""
    result = {
        "sources": [],
        "raw_content": "",
        "search_executed": False,
        "provider": "serper",
        "error": None,
    }

    if not api_key:
        result["error"] = "SERPER_API_KEY is not configured."
        return result

    try:
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
            timeout=timeout,
        )

        if resp.status_code == 200:
            data = resp.json()
            result["search_executed"] = True
            for item in data.get("organic", []):
                result["sources"].append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })
        elif resp.status_code == 401:
            result["error"] = "Serper API key is invalid."
        elif resp.status_code == 429:
            result["error"] = "Serper rate limit exceeded."
        else:
            result["error"] = f"Serper search returned HTTP {resp.status_code}."
    except Exception as e:
        result["error"] = f"Serper search failed: {type(e).__name__}"

    return result


# ---------------------------------------------------------------------------
# 4. DuckDuckGo HTML Search Adapter (Zero-key fallback)
# ---------------------------------------------------------------------------

def search_duckduckgo(query: str, max_results: int = 5, timeout: int = 15) -> dict:
    """Execute real web search using DuckDuckGo HTML endpoint without requiring an API key."""
    result = {
        "sources": [],
        "raw_content": "",
        "search_executed": False,
        "provider": "duckduckgo",
        "error": None,
    }

    try:
        resp = httpx.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            timeout=timeout,
        )

        if resp.status_code != 200:
            result["error"] = f"DuckDuckGo search returned HTTP {resp.status_code}."
            return result

        titles = re.findall(r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', resp.text)
        snippets = re.findall(r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', resp.text, re.DOTALL)

        count = min(len(titles), len(snippets), max_results)
        for i in range(count):
            url, raw_title = titles[i]
            title = unescape(re.sub(r'<[^>]+>', '', raw_title).strip())
            snippet = unescape(re.sub(r'<[^>]+>', '', snippets[i]).strip())

            # Unwrap redirect if present
            if "uddg=" in url:
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                url = parsed.get("uddg", [url])[0]

            if title and url:
                result["sources"].append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                })

        if result["sources"]:
            result["search_executed"] = True
            # Build synthesis of snippets
            result["raw_content"] = "\n\n".join(
                f"[{s['title']}]: {s['snippet']}" for s in result["sources"] if s.get("snippet")
            )
        else:
            result["error"] = "DuckDuckGo search returned no organic results for this query."

    except Exception as e:
        result["error"] = f"DuckDuckGo search failed: {type(e).__name__}"

    return result


# ---------------------------------------------------------------------------
# Master Retrieval Dispatcher
# ---------------------------------------------------------------------------

def execute_web_search(
    query: str,
    groq_client=None,
    groq_search_model: str = "openai/gpt-oss-120b",
    timeout: int = 30,
) -> dict:
    """Master retrieval function.

    Attempts retrieval in priority order:
    1. Explicit provider configured in SEARCH_PROVIDER env (tavily, serper, duckduckgo, groq)
    2. If groq: try Groq browser_search.
       If Groq returns 404, 400, or 429: fallback to alternative search (Tavily/Serper if configured, else DuckDuckGo).
    3. Fails cleanly with clear provider error if no sources could be retrieved.
    """
    provider_pref = os.getenv("SEARCH_PROVIDER", "groq").lower().strip()
    tavily_key = os.getenv("TAVILY_API_KEY", "").strip()
    serper_key = os.getenv("SERPER_API_KEY", "").strip()

    # 1. Direct provider selection
    if provider_pref == "tavily" and tavily_key:
        return search_tavily(query, tavily_key, timeout=timeout)
    if provider_pref == "serper" and serper_key:
        return search_serper(query, serper_key, timeout=timeout)
    if provider_pref == "duckduckgo":
        return search_duckduckgo(query, timeout=timeout)

    # 2. Groq Browser Search (default when Groq client available)
    if groq_client:
        groq_result = search_groq_browser(groq_client, query, search_model=groq_search_model, timeout=timeout)
        if groq_result["sources"]:
            return groq_result

        # If Groq search failed (e.g. 404 model not found, 429 rate limit, 400 unsupported tool):
        logger.warning("Groq browser search failed: %s. Attempting fallback retrieval.", groq_result.get("error"))

        # Fallback 2a: Tavily if key present
        if tavily_key:
            logger.info("Attempting fallback to Tavily search.")
            t_res = search_tavily(query, tavily_key, timeout=timeout)
            if t_res["sources"]:
                return t_res

        # Fallback 2b: Serper if key present
        if serper_key:
            logger.info("Attempting fallback to Serper search.")
            s_res = search_serper(query, serper_key, timeout=timeout)
            if s_res["sources"]:
                return s_res

        # Fallback 2c: DuckDuckGo zero-key search
        logger.info("Attempting fallback to DuckDuckGo search.")
        ddg_res = search_duckduckgo(query, timeout=timeout)
        if ddg_res["sources"]:
            # Note in raw_content that fallback search was used
            ddg_res["fallback_from"] = groq_result.get("error")
            return ddg_res

        # If all fallbacks failed, return the primary Groq error
        return groq_result

    # 3. If no Groq client, try DuckDuckGo or configured search keys
    if tavily_key:
        return search_tavily(query, tavily_key, timeout=timeout)
    if serper_key:
        return search_serper(query, serper_key, timeout=timeout)

    return search_duckduckgo(query, timeout=timeout)
