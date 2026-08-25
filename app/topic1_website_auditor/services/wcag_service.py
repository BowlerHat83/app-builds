import requests
from bs4 import BeautifulSoup

def analyze_wcag(url: str):
    if not url:
        return {"critical": "No Data", "serious": "No Data", "moderate": "No Data", "minor": "No Data"}
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        if res.status_code != 200:
            return {"critical": "No Data", "serious": "No Data", "moderate": "No Data", "minor": "No Data"}
        
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Count accessibility flaws
        images_without_alt = len([img for img in soup.find_all("img") if not img.get("alt")])
        inputs_without_label = len([inp for inp in soup.find_all("input") if not inp.get("id") or not soup.find("label", attrs={"for": inp.get("id")})])
        missing_lang = 1 if not soup.find("html", attrs={"lang": True}) else 0
        missing_title = 1 if not soup.find("title") else 0

        return {
            "critical": missing_title + missing_lang,
            "serious": inputs_without_label,
            "moderate": images_without_alt,
            "minor": 0
        }
    except Exception:
        return {"critical": "No Data", "serious": "No Data", "moderate": "No Data", "minor": "No Data"}
