from bs4 import BeautifulSoup
from curl_cffi import requests
from pydantic import BaseModel
from typing import List, Optional

class WCAGIssue(BaseModel):
    code: str
    description: str
    impact: str
    element: Optional[str] = None

class WCAGAuditResult(BaseModel):
    url: str
    score: int
    total_issues: int
    issues: List[WCAGIssue]

def run_wcag_checks(url: str, html_content: str) -> WCAGAuditResult:
    soup = BeautifulSoup(html_content, "html.parser")
    issues = []

    # 1. Image Alt Attributes
    images = soup.find_all("img")
    for img in images:
        if not img.has_attr("alt"):
            issues.append(WCAGIssue(
                code="1.1.1 Non-text Content",
                description="Image missing alt attribute",
                impact="Critical",
                element=str(img)[:100]
            ))

    # 2. Page Title
    if not soup.find("title") or not soup.find("title").string:
        issues.append(WCAGIssue(
            code="2.4.2 Page Titled",
            description="Document missing <title> tag or title is empty",
            impact="Serious",
            element="<head>"
        ))

    # 3. HTML Language Attribute
    html_tag = soup.find("html")
    if not html_tag or not html_tag.has_attr("lang"):
        issues.append(WCAGIssue(
            code="3.1.1 Language of Page",
            description="<html> tag missing lang attribute",
            impact="Moderate",
            element="<html>"
        ))

    total = len(issues)
    score = max(0, 100 - (total * 5))

    return WCAGAuditResult(
        url=url,
        score=score,
        total_issues=total,
        issues=issues
    )

async def fetch_and_audit_wcag(url: str) -> WCAGAuditResult:
    response = requests.get(url, impersonate="chrome120", timeout=15)
    response.raise_for_status()
    return run_wcag_checks(url, response.text)
