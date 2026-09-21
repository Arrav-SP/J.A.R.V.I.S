"""Live web search tool for JARVIS using DuckDuckGo Lite (zero-key)."""

from __future__ import annotations

from dataclasses import dataclass
import html
import logging
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from app.tools.schemas import BaseTool, ToolDefinition, ToolParameter

logger = logging.getLogger("jarvis.tools.search")


@dataclass
class SearchResultItem:
    """A single web search result item."""

    title: str
    snippet: str
    url: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "snippet": self.snippet,
            "url": self.url,
        }


class WebSearchTool(BaseTool):
    """Searches the live web using DuckDuckGo Lite without needing API keys."""

    def __init__(self, timeout_seconds: float = 8.0) -> None:
        self.timeout_seconds = timeout_seconds

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_search",
            description="Search the live internet for recent information, facts, scores, news, or general knowledge.",
            category="web",
            parameters=[
                ToolParameter(
                    name="query",
                    type_name="string",
                    description="Search query string (e.g. 'who won IPL 2024', 'latest news Python 3.14').",
                    required=True,
                ),
                ToolParameter(
                    name="max_results",
                    type_name="integer",
                    description="Maximum number of search results to retrieve (1-10).",
                    required=False,
                    default=4,
                ),
            ],
        )

    def run(self, query: str, max_results: int = 4, **kwargs: Any) -> Dict[str, Any]:
        """Execute web search and return structured snippets."""
        clean_query = query.strip()
        if not clean_query:
            return {"query": "", "results": [], "summary": "Empty search query provided."}

        # Normalize common voice recognition merges like "IPL2025" -> "IPL 2025"
        clean_query = re.sub(r"\b([a-zA-Z]+)(\d{4})\b", r"\1 \2", clean_query)

        # 1. Primary: DuckDuckGo Lite POST
        items: List[SearchResultItem] = []
        try:
            items = self._search_duckduckgo_lite(clean_query, max_results=max_results)
        except Exception as err:
            logger.warning("DuckDuckGo Lite search failed: %s.", err)

        # 2. Fallback: DuckDuckGo HTML GET endpoint
        if not items:
            try:
                items = self._search_duckduckgo_html(clean_query, max_results=max_results)
            except Exception as err:
                logger.warning("DuckDuckGo HTML fallback failed: %s.", err)

        # 3. Fallback: DuckDuckGo Instant Answer API
        if not items:
            try:
                items = self._search_instant_answer(clean_query)
            except Exception as err:
                logger.warning("Instant Answer fallback failed: %s.", err)

        summary_lines = []
        for i, item in enumerate(items, 1):
            summary_lines.append(f"[{i}] {item.title}: {item.snippet}")

        summary = "\n".join(summary_lines) if summary_lines else f"No search results found for '{clean_query}'."

        return {
            "query": clean_query,
            "count": len(items),
            "results": [item.to_dict() for item in items],
            "summary": summary,
        }

    def _search_duckduckgo_html(self, query: str, max_results: int = 4) -> List[SearchResultItem]:
        """Fallback to DuckDuckGo HTML GET endpoint."""
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            content = resp.read().decode("utf-8", errors="ignore")

        items: List[SearchResultItem] = []
        snippets = re.findall(r"class=[\'\"]result__snippet[\'\"][^>]*>(.*?)</a>", content, flags=re.DOTALL | re.IGNORECASE)
        links = re.findall(r"<a\s+([^>]*class=[\'\"]result__url[\'\"][^>]*)>(.*?)</a>", content, flags=re.DOTALL | re.IGNORECASE)

        for i in range(min(len(snippets), max_results)):
            clean_snip = html.unescape(re.sub(r"<[^>]+>", "", snippets[i]).strip())
            title = f"Result {i+1}"
            link = ""
            if i < len(links):
                attr, text = links[i]
                href_m = re.search(r"href=[\'\"]([^\'\"]+)[\'\"]", attr)
                if href_m:
                    link = href_m.group(1)
                t_clean = html.unescape(re.sub(r"<[^>]+>", "", text).strip())
                if t_clean:
                    title = t_clean

            if clean_snip:
                items.append(SearchResultItem(title=title, snippet=clean_snip, url=link))

        return items

    def _search_duckduckgo_lite(self, query: str, max_results: int = 4) -> List[SearchResultItem]:
        """Scrape DuckDuckGo Lite HTML endpoint for search snippets."""
        url = "https://lite.duckduckgo.com/lite/"
        data = urllib.parse.urlencode({"q": query}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html,application/xhtml+xml,application/xml",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            content = resp.read().decode("utf-8", errors="ignore")

        items: List[SearchResultItem] = []

        # Find result snippets in DuckDuckGo Lite table: <td class='result-snippet'>...</td>
        snippet_matches = re.findall(r"class=[\'\"]result-snippet[\'\"][^>]*>(.*?)</td>", content, flags=re.DOTALL | re.IGNORECASE)
        # Find result links: <a ... class='result-link' ...>...</a> (attributes in any order)
        link_matches = re.findall(r"<a\s+([^>]*class=[\'\"]result-link[\'\"][^>]*)>(.*?)</a>", content, flags=re.DOTALL | re.IGNORECASE)

        for i in range(min(len(snippet_matches), max_results)):
            raw_snippet = snippet_matches[i]
            clean_snippet = html.unescape(re.sub(r"<[^>]+>", "", raw_snippet).strip())

            title = f"Result {i+1}"
            link = ""
            if i < len(link_matches):
                attr, text = link_matches[i]
                href_m = re.search(r"href=[\'\"]([^\'\"]+)[\'\"]", attr)
                if href_m:
                    link = href_m.group(1)
                t_clean = html.unescape(re.sub(r"<[^>]+>", "", text).strip())
                if t_clean:
                    title = t_clean

            if clean_snippet:
                items.append(SearchResultItem(title=title, snippet=clean_snippet, url=link))

        return items

    def _search_instant_answer(self, query: str) -> List[SearchResultItem]:
        """Fallback to DuckDuckGo Instant Answer JSON API."""
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "JARVIS-Assistant/1.0"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            import json
            data = json.loads(resp.read().decode("utf-8"))

        abstract = data.get("AbstractText", "").strip()
        source = data.get("AbstractSource", "DuckDuckGo")
        source_url = data.get("AbstractURL", "")

        if abstract:
            return [SearchResultItem(title=f"{source} Summary", snippet=abstract, url=source_url)]

        related = data.get("RelatedTopics", [])
        items = []
        for topic in related[:3]:
            text = topic.get("Text", "").strip()
            first_url = topic.get("FirstURL", "")
            if text:
                items.append(SearchResultItem(title="Related Topic", snippet=text, url=first_url))

        return items
