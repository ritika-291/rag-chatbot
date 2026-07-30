from ddgs import DDGS
import logging
import time
import requests
import re
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

def _scrape_ddg_html_first_result(query: str, timeout: float = 5.0) -> str:
    """Fallback: query DuckDuckGo's HTML endpoint and return first target page snippet.

    This avoids adding BeautifulSoup as a dependency by using simple regex parsing
    that is sufficient to extract the first result link in most cases.
    """
    try:
        params = {"q": query}
        url = f"https://html.duckduckgo.com/html?{urlencode(params)}"
        headers = {"User-Agent": "docubuddy/1.0 (+https://example.local)"}
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()

        # Find first external link in the results HTML
        # This is a best-effort approach: look for hrefs and skip DuckDuckGo internal links
        hrefs = re.findall(r'href\s*=\s*"(https?://[^"]+)"', r.text)
        for h in hrefs:
            if "duckduckgo.com" in h:
                continue
            try:
                page = requests.get(h, headers=headers, timeout=timeout)
                page.raise_for_status()
                body = page.text
                # Rough tag removal without bs4
                body = re.sub(r'<script[^>]*>.*?</script>', ' ', body, flags=re.IGNORECASE|re.DOTALL)
                body = re.sub(r'<style[^>]*>.*?</style>', ' ', body, flags=re.IGNORECASE|re.DOTALL)
                body = re.sub(r'<[^>]+>', ' ', body)
                snippet = re.sub(r"\s+", " ", body).strip()[:1500]
                return snippet + "\n\nSource: " + h
            except Exception:
                continue

        return "No useful result found online."
    except Exception as e:
        logger.warning("DDG HTML scrape fallback failed: %s", e)
        return f"Web search error (fallback) : {str(e)}"


def search_web(query: str, retries: int = 3, backoff: float = 1.5) -> str:
    """Search DuckDuckGo (via DDGS) with simple retries and backoff.

    Returns the top 5 results or a clear error message.
    Falls back to a lightweight HTML-scrape of DuckDuckGo when DDGS fails.
    """
    for attempt in range(1, retries + 1):
        try:
            with DDGS() as ddgs:
                # Fetch top 5 results to provide better context
                results = list(ddgs.text(query, max_results=5))

            if results:
                formatted = []
                for idx, r in enumerate(results, 1):
                    title = r.get("title", "No Title")
                    snippet = r.get("body", "No Snippet")
                    link = r.get("href", "No Link")
                    formatted.append(f"Result {idx}:\nTitle: {title}\nSnippet: {snippet}\nSource: {link}")
                return "\n\n".join(formatted)

            # no results but no exception -> try HTML fallback
            logger.info("DDGS returned no results, trying HTML fallback")
            return _scrape_ddg_html_first_result(query)

        except Exception as e:
            logger.warning("DuckDuckGo search failed (attempt %d/%d): %s", attempt, retries, e)
            # last attempt -> try fallback once before giving up
            if attempt == retries:
                try:
                    return _scrape_ddg_html_first_result(query)
                except Exception:
                    return f"Web search error after {retries} attempts: {str(e)}"

            # backoff before retrying
            try:
                sleep_time = backoff ** attempt
                time.sleep(sleep_time)
            except Exception:
                # if sleep fails for some reason, continue immediately
                continue
