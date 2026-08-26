import requests

def check_ssl(url: str):
    if not url: return "No Data"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        target = url if url.startswith("http") else f"https://{url}"
        res = requests.get(target, headers=headers, timeout=5, allow_redirects=True)
        return "Valid" if res.url.startswith("https://") else "Invalid"
    except Exception:
        return "No Data"
