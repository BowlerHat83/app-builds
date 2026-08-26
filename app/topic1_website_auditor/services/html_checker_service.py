import requests
from bs4 import BeautifulSoup

def check_html_syntax(url: str):
    if not url: return "No Data"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            return "Valid" if soup.find("html") else "Errors Found"
        return "No Data"
    except Exception:
        return "No Data"
