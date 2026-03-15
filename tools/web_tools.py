import re
import html
import urllib.parse

try:
    import requests
except Exception:  # pragma: no cover - optional dependency
    requests = None

from llm import ask_coder


_DDG_URL = "https://duckduckgo.com/html/?q="

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120 Safari/537.36"
)

_BLOCKED_DOMAINS = {
    "duckduckgo.com",
    "duckduckgo.com.cn",
    "duckduckgo.co",
    "googlesyndication.com",
    "doubleclick.net",
    "adservice.google.com",
    "adsystem.com",
    "adnxs.com",
}

_TRACKING_PARAMS = {
    "gclid",
    "fbclid",
    "yclid",
    "mc_cid",
    "mc_eid",
}


def _safe_get(url: str, timeout: int = 10) -> str:
    if not url:
        return ""
    if requests is None:
        return ""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return ""


def _unwrap_ddg_url(url: str) -> str:
    if "uddg=" not in url:
        return url
    try:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        uddg = qs.get("uddg", [])
        if uddg:
            return urllib.parse.unquote(uddg[0])
    except Exception:
        return url
    return url


def _strip_tracking(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return url
    if not parsed.query:
        return url
    qs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered = []
    for k, v in qs:
        key = k.lower()
        if key in _TRACKING_PARAMS or key.startswith("utm_"):
            continue
        filtered.append((k, v))
    new_query = urllib.parse.urlencode(filtered, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


def _is_valid_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.netloc:
        return False
    host = parsed.netloc.lower()
    for domain in _BLOCKED_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return False
    return True


def search_web(query: str, top_k: int = 5):
    if not query:
        return []
    url = _DDG_URL + urllib.parse.quote_plus(query)
    html_doc = _safe_get(url)
    if not html_doc:
        return []

    results = []
    try:
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(html_doc, "html.parser")
        for res in soup.select("div.result"):
            classes = " ".join(res.get("class", []))
            if "result--ad" in classes or "result__ad" in classes:
                continue
            a = res.select_one("a.result__a")
            if not a:
                continue
            title = a.get_text(" ", strip=True)
            href = a.get("href", "").strip()
            href = _unwrap_ddg_url(html.unescape(href))
            href = _strip_tracking(href)
            if not _is_valid_url(href):
                continue
            snippet_el = res.select_one(".result__snippet")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
            if title and href:
                results.append({"title": title, "url": href, "snippet": snippet})
            if len(results) >= top_k:
                break
        return results
    except Exception:
        pass

    for match in re.finditer(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html_doc,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        href = html.unescape(match.group(1))
        href = _unwrap_ddg_url(href)
        href = _strip_tracking(href)
        if not _is_valid_url(href):
            continue
        title = re.sub(r"<.*?>", "", match.group(2))
        title = html.unescape(title).strip()
        if title and href:
            results.append({"title": title, "url": href, "snippet": ""})
        if len(results) >= top_k:
            break

    return results


def fetch_page(url: str):
    return _safe_get(url, timeout=10)


def extract_text(html_doc: str):
    if not html_doc:
        return ""
    try:
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(html_doc, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
    except Exception:
        text = re.sub(r"<script.*?</script>", " ", html_doc, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()

    return text[:5000]


def summarize_text(text: str):
    if not text:
        return ""
    prompt = (
        "Summarize the following text concisely in 4-6 bullet points.\n\n"
        f"{text[:5000]}"
    )
    return ask_coder(prompt).strip()
