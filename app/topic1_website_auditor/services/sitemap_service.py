import requests

def check_sitemap(url: str):
    if not url: return "Not Found"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    base_url = url.rstrip('/')
    sitemap_paths = ["/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"]
    
    for path in sitemap_paths:
        try:
            target = f"{base_url}{path}"
            res = requests.get(target, headers=headers, timeout=5, allow_redirects=True)
            if res.status_code == 200 and ("xml" in res.headers.get("Content-Type", "") or "<sitemap" in res.text.lower()):
                return "Found"
        except Exception:
            continue
    return "Not Found"
