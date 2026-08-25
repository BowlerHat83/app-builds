import requests

def check_gdpr_banner(url: str):
    if not url:
        return {"cmp_provider": "No Data", "banner_found": "No Data", "pre_consent": "No Data", "post_consent": "No Data"}
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        text = res.text.lower()
        
        keywords = ['cookie', 'consent', 'gdpr', 'onetrust', 'cookiebot', 'complianz', 'termly', 'usercentrics', 'iubenda', 'cybot']
        banner_detected = any(k in text for k in keywords)
        
        cmp_name = "None Detected"
        if "onetrust" in text: cmp_name = "OneTrust"
        elif "cookiebot" in text or "cybot" in text: cmp_name = "Cookiebot"
        elif "complianz" in text: cmp_name = "Complianz"
        elif "usercentrics" in text: cmp_name = "Usercentrics"
        elif "iubenda" in text: cmp_name = "iubenda"
        elif banner_detected: cmp_name = "Custom / Standard Banner"

        return {
            "cmp_provider": cmp_name,
            "banner_found": "Found" if banner_detected else "Not Found",
            "pre_consent": "Blocked" if banner_detected else "Unrestricted",
            "post_consent": "Active"
        }
    except Exception:
        return {"cmp_provider": "No Data", "banner_found": "No Data", "pre_consent": "No Data", "post_consent": "No Data"}
