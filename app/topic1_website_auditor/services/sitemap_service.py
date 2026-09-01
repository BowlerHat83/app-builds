import xml.etree.ElementTree as ET
import httpx

# Standard browser User-Agent prevents websites from blocking HTTP requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


async def discover_sitemap_url(input_url: str) -> str:
    """Discovers the sitemap location via robots.txt or common fallback paths."""
    input_url = input_url.rstrip("/")

    # If user explicitly points to an XML file, try that first
    if input_url.endswith(".xml"):
        return input_url

    async with httpx.AsyncClient(headers=HEADERS, timeout=10.0, follow_redirects=True) as client:
        # 1. Check robots.txt for 'Sitemap:' declaration
        try:
            robots_res = await client.get(f"{input_url}/robots.txt")
            if robots_res.status_code == 200:
                for line in robots_res.text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        return line.split(":", 1)[1].strip()
        except Exception:
            pass

        # 2. Check standard fallback locations
        candidates = [
            f"{input_url}/sitemap.xml",
            f"{input_url}/sitemap_index.xml",
            f"{input_url}/sitemap-index.xml",
        ]
        for candidate in candidates:
            try:
                res = await client.head(candidate)
                if res.status_code == 200:
                    return candidate
            except Exception:
                continue

    return f"{input_url}/sitemap.xml"


async def fetch_sitemap_urls_with_lastmod(sitemap_url: str) -> list[dict]:
    """
    Same crawl as fetch_sitemap_urls below, but also captures each entry's
    <lastmod> date when the sitemap provides one - a real content-freshness
    signal that was being read right past (the XML was already being
    parsed for <loc>, <lastmod> just wasn't looked at). Returns
    [{"url": ..., "lastmod": "YYYY-MM-DD" or None}, ...] - a separate
    function rather than changing fetch_sitemap_urls' return shape, since
    that one has another caller (sitemap_routes.py) expecting a plain
    list[str].
    """
    target_url = await discover_sitemap_url(sitemap_url)

    async with httpx.AsyncClient(headers=HEADERS, timeout=10.0, follow_redirects=True) as client:
        response = await client.get(target_url)
        if response.status_code == 404:
            return []
        response.raise_for_status()

    root = ET.fromstring(response.content)

    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}")[0] + "}"

    entries = []

    for url_node in root.findall(f".//{namespace}url"):
        loc = url_node.find(f"{namespace}loc")
        if loc is not None and loc.text:
            lastmod_node = url_node.find(f"{namespace}lastmod")
            lastmod = lastmod_node.text.strip() if lastmod_node is not None and lastmod_node.text else None
            entries.append({"url": loc.text.strip(), "lastmod": lastmod})

    if not entries:
        for sitemap_node in root.findall(f".//{namespace}sitemap"):
            loc = sitemap_node.find(f"{namespace}loc")
            if loc is not None and loc.text:
                try:
                    sub_entries = await fetch_sitemap_urls_with_lastmod(loc.text.strip())
                    entries.extend(sub_entries)
                except Exception:
                    continue

    # De-dupe by URL (a nested sitemap index can list the same page twice),
    # keeping the first lastmod seen for each.
    seen = {}
    for e in entries:
        if e["url"] not in seen:
            seen[e["url"]] = e
    return list(seen.values())


async def fetch_sitemap_urls(sitemap_url: str) -> list[str]:
    """Fetches a sitemap XML and extracts all page URLs."""
    target_url = await discover_sitemap_url(sitemap_url)

    async with httpx.AsyncClient(headers=HEADERS, timeout=10.0, follow_redirects=True) as client:
        response = await client.get(target_url)
        response.raise_for_status()

    # Parse XML content
    root = ET.fromstring(response.content)

    # Clean namespace (e.g., {http://www.sitemaps.org/schemas/sitemap/0.9})
    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}")[0] + "}"

    urls = []

    # Parse standard sitemap <url><loc>...</loc></url>
    for url_node in root.findall(f".//{namespace}url"):
        loc = url_node.find(f"{namespace}loc")
        if loc is not None and loc.text:
            urls.append(loc.text.strip())

    # Parse sitemap index <sitemap><loc>...</loc></sitemap>
    if not urls:
        for sitemap_node in root.findall(f".//{namespace}sitemap"):
            loc = sitemap_node.find(f"{namespace}loc")
            if loc is not None and loc.text:
                # Recursively fetch nested sitemaps
                try:
                    sub_urls = await fetch_sitemap_urls(loc.text.strip())
                    urls.extend(sub_urls)
                except Exception:
                    continue

    return list(set(urls))