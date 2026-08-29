import asyncio
import traceback
from typing import List, Dict, Optional
from pydantic import BaseModel
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from app.common.browser_lock import CHROMIUM_SLOT, LOW_MEMORY_CHROMIUM_ARGS


class MandatoryPolicies(BaseModel):
    privacy_policy: bool
    cookie_policy: bool
    terms_of_service: bool
    found_links: Dict[str, Optional[str]]


class BannerDetails(BaseModel):
    banner_detected: bool
    cmp_provider: Optional[str]
    has_accept_button: bool
    has_reject_button: bool


class GDPRCheckResult(BaseModel):
    url: str
    is_gdpr_compliant: bool
    score: float
    policies: MandatoryPolicies
    banner: BannerDetails
    pre_consent_cookie_count: int
    post_consent_cookie_count: int
    non_essential_preconsent_risk: bool
    cookies_detected: List[Dict[str, str]]


CMP_SIGNATURES = {
    "Cookiebot": ["cookiebot"],
    "OneTrust": ["onetrust", "optanonconsent"],
    "Termly": ["termly"],
    "Usercentrics": ["usercentrics"],
    "Klaro": ["klaro"],
    "Didomi": ["didomi"],
    "Iubenda": ["iubenda"],
    "Complianz": ["complianz"],
}


def _sync_run_gdpr_audit(url: str) -> GDPRCheckResult:
    if not url.startswith("http"):
        url = "https://" + url

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            # --disable-dev-shm-usage matters a lot in Docker specifically -
            # containers default to a tiny 64MB /dev/shm and Chromium leans
            # on shared memory heavily, so without this it can crash/hang
            # under real load instead of just using more of the host's
            # regular (much larger) memory.
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"] + LOW_MEMORY_CHROMIUM_ARGS
        )
        try:
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(2000)
            except PlaywrightTimeoutError:
                pass

            html_content = page.content()
            soup = BeautifulSoup(html_content, "html.parser")

            # 1. Policy Link Checks
            links = soup.find_all("a", href=True)
            found_links = {"privacy_policy": None, "cookie_policy": None, "terms_of_service": None}

            for a in links:
                href = a["href"].strip()
                text = a.text.lower()
                if "privacy" in text or "privacy" in href:
                    found_links["privacy_policy"] = href
                elif "cookie" in text or "cookie" in href:
                    found_links["cookie_policy"] = href
                elif "terms" in text or "terms" in href or "tos" in href:
                    found_links["terms_of_service"] = href

            policies = MandatoryPolicies(
                privacy_policy=found_links["privacy_policy"] is not None,
                cookie_policy=found_links["cookie_policy"] is not None,
                terms_of_service=found_links["terms_of_service"] is not None,
                found_links=found_links,
            )

            # 2. Pre-Consent Cookies
            pre_cookies = context.cookies()
            pre_consent_count = len(pre_cookies)

            # 3. Detect CMP Provider
            detected_cmp = None
            html_lower = html_content.lower()
            for provider, keywords in CMP_SIGNATURES.items():
                if any(kw in html_lower for kw in keywords):
                    detected_cmp = provider
                    break

            # 4. Banner & Accept/Reject Buttons
            banner_detected = False
            has_accept = False
            has_reject = False

            buttons = page.query_selector_all("button, a, input[type=\"button\"]")
            accept_button_ref = None

            for btn in buttons:
                try:
                    txt = btn.inner_text().lower().strip()
                    if any(k in txt for k in ["accept", "agree", "allow all", "accept all"]):
                        has_accept = True
                        accept_button_ref = btn
                        banner_detected = True
                    if any(k in txt for k in ["decline", "reject", "deny", "disagree", "reject all"]):
                        has_reject = True
                        banner_detected = True
                except Exception:
                    continue

            banner_info = BannerDetails(
                banner_detected=banner_detected or detected_cmp is not None,
                cmp_provider=detected_cmp if detected_cmp else ("Custom/Unknown" if banner_detected else "None"),
                has_accept_button=has_accept,
                has_reject_button=has_reject,
            )

            # 5. Post-Consent Cookies (Simulate Click)
            if accept_button_ref:
                try:
                    accept_button_ref.click(timeout=2000)
                    page.wait_for_timeout(2000)
                except Exception:
                    pass

            post_cookies = context.cookies()
            post_consent_count = len(post_cookies)

        finally:
            browser.close()

        risk_preconsent = pre_consent_count > 3

        score = 100.0
        if not policies.privacy_policy: score -= 25.0
        if not banner_info.banner_detected: score -= 30.0
        if not banner_info.has_reject_button: score -= 15.0
        if risk_preconsent: score -= 20.0

        score = max(0.0, score)

        cookie_list = [
            {"name": c["name"], "domain": c["domain"], "path": c["path"], "secure": str(c["secure"])}
            for c in post_cookies
        ]

        return GDPRCheckResult(
            url=url,
            is_gdpr_compliant=score >= 70.0,
            score=round(score, 2),
            policies=policies,
            banner=banner_info,
            pre_consent_cookie_count=pre_consent_count,
            post_consent_cookie_count=post_consent_count,
            non_essential_preconsent_risk=risk_preconsent,
            cookies_detected=cookie_list,
        )


async def run_gdpr_audit(url: str) -> GDPRCheckResult:
    # Only one Chromium-based check runs at a time - see app/common/browser_lock.py
    async with CHROMIUM_SLOT:
        return await asyncio.to_thread(_sync_run_gdpr_audit, url)

