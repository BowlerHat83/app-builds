"""
Accessibility (WCAG) checker.

This runs axe-core - the open-source engine behind Chrome DevTools'
Accessibility panel, Lighthouse's accessibility score, and most commercial
scanners - against a live, rendered page, IF a copy of it has been placed at
app/topic1_website_auditor/vendor/axe.min.js. Neither this backend's host
machine nor the sandbox this was built in has general internet/package
access (pip, npm, PyPI and CDN fetches for axe-core all fail with
network/proxy errors here), so that file has to be supplied by hand - see
README/instructions for exactly how.

If that file isn't present, this falls back automatically to a hand-written
ruleset (~16 checks covering the same broad areas: missing alt text, form
labels, heading structure, accessible names, focus order, captions, and a
real from-scratch WCAG contrast-ratio calculator implementing the W3C's own
relative-luminance formula) run against the same real Playwright-rendered
page. Either way the result shape (score, issues, impact) is identical to
the rest of the app - only WCAGAuditResult.engine differs, so the frontend
can show which one actually ran.

Both engines audit a single page (whatever target_url is) - neither does a
full-site crawl on its own. axe-core itself has no notion of "the whole
site"; it audits whatever DOM it's run against at that moment. Multi-page
coverage would mean wrapping this in a loop over the sitemap URLs Topic 1
already discovers - that's a separate, bigger change (more pages = much
longer audit time, and a different results shape than "one score per
metric"), not something turned on by adding axe-core.
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.common.browser_lock import CHROMIUM_SLOT, LOW_MEMORY_CHROMIUM_ARGS

# Where to drop axe.min.js to switch this over to the real engine - see the
# module docstring above. No code changes needed once it's here; this is
# checked fresh on every audit run, not just at import time.
_VENDOR_AXE_PATH = Path(__file__).resolve().parent.parent / "vendor" / "axe.min.js"


class WCAGIssue(BaseModel):
    code: str
    description: str
    impact: str
    element: Optional[str] = None
    occurrences: int = 1


class WCAGAuditResult(BaseModel):
    url: str
    score: int
    total_issues: int
    total_occurrences: int
    issues: List[WCAGIssue]
    engine: str = "custom-ruleset"
    engine_note: Optional[str] = None


# Points deducted per issue found, by severity - a Critical issue costs
# more than a Minor one, so the four categories genuinely affect the score
# instead of just being cosmetic labels. Used for both engines so scores
# stay comparable to each other and to the frontend's score-composition bar.
_SEVERITY_WEIGHT = {"critical": 8, "serious": 5, "moderate": 3, "minor": 1}

_COOKIE_ACCEPT_LABELS = ["Accept all", "Accept All", "I agree", "Allow all", "Allow All", "Got it", "OK", "Accept"]


def _dismiss_cookie_banner(page) -> None:
    """A consent banner still open when checks run can itself introduce
    false contrast/overlap results and hides real content behind it."""
    try:
        for label in _COOKIE_ACCEPT_LABELS:
            btn = page.get_by_role("button", name=label, exact=False)
            if btn.count() > 0:
                btn.first.click(timeout=1500)
                page.wait_for_timeout(500)
                return
    except Exception:
        pass


def _axe_violations_to_issues(violations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """axe.run() returns { violations: [...] } where each violation covers
    potentially many DOM nodes - reshaped here into the same
    {code, description, impact, element, occurrences} shape the custom
    ruleset produces, so the rest of the app doesn't need to know which
    engine actually ran."""
    issues: List[Dict[str, Any]] = []
    for v in violations:
        nodes = v.get("nodes") or []
        first_html = (nodes[0].get("html") if nodes else None) or ""
        issues.append(
            {
                "code": v.get("id", "unknown"),
                "description": v.get("help") or v.get("description") or "Accessibility issue",
                "impact": (v.get("impact") or "moderate").capitalize(),
                "element": first_html[:150] or None,
                "occurrences": len(nodes) or 1,
            }
        )
    return issues


# Runs entirely inside the rendered page via page.evaluate() - one round
# trip instead of many, and every check here sees real computed styles /
# visibility, which is what a static-HTML check structurally cannot do.
# This is the fallback used only when axe.min.js isn't available - see
# _run_wcag_checks_sync below.
_CHECK_SCRIPT = r"""
() => {
  const issues = [];
  const push = (code, description, impact, el, occurrences) => {
    issues.push({
      code,
      description,
      impact,
      element: el ? (el.outerHTML || "").slice(0, 150) : null,
      occurrences: occurrences || 1,
    });
  };
  const isVisible = (el) => {
    const style = getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") return false;
    if (parseFloat(style.opacity) === 0) return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  };
  // Deliberately NOT checking bounding-box size here, unlike isVisible()
  // above - an empty <a></a> with no text/image content collapses to zero
  // size *because* it has no accessible content, which is exactly the bug
  // this check exists to catch. It can still be a real stop in the tab
  // order (a screen reader announces nothing there), so excluding it for
  // being zero-size would hide the very elements this check is for.
  const isNotHidden = (el) => {
    const style = getComputedStyle(el);
    return style.display !== "none" && style.visibility !== "hidden" && parseFloat(style.opacity) !== 0;
  };
  const hasAccessibleName = (el) => {
    if ((el.getAttribute("aria-label") || "").trim()) return true;
    if ((el.getAttribute("aria-labelledby") || "").trim()) return true;
    if ((el.textContent || "").trim()) return true;
    const img = el.querySelector("img[alt]");
    if (img && (img.getAttribute("alt") || "").trim()) return true;
    return false;
  };

  // 1. Images missing alt (decorative images correctly excluded via
  // role="presentation"/aria-hidden, which a static-HTML-only check has
  // no reliable way to combine with "is this image actually rendered".
  let missingAlt = [];
  document.querySelectorAll("img").forEach((img) => {
    if (img.getAttribute("role") === "presentation" || img.getAttribute("aria-hidden") === "true") return;
    if (!img.hasAttribute("alt")) missingAlt.push(img);
  });
  if (missingAlt.length) push("1.1.1 Non-text Content", "Image missing alt attribute", "Critical", missingAlt[0], missingAlt.length);

  // 2. Page title
  const title = document.querySelector("title");
  if (!title || !title.textContent.trim()) push("2.4.2 Page Titled", "Document missing <title> tag or title is empty", "Serious", null, 1);

  // 3. HTML lang attribute
  const htmlTag = document.documentElement;
  if (!htmlTag.hasAttribute("lang") || !htmlTag.getAttribute("lang").trim()) {
    push("3.1.1 Language of Page", "<html> tag missing lang attribute", "Moderate", htmlTag, 1);
  }

  // 4. Links/buttons with no accessible name at all
  let noName = [];
  document.querySelectorAll("a[href], button").forEach((el) => {
    if (!isNotHidden(el)) return;
    if (!hasAccessibleName(el)) noName.push(el);
  });
  if (noName.length) push("4.1.2 Name, Role, Value", "Link/button has no accessible text, aria-label, or labelled image content", "Critical", noName[0], noName.length);

  // 5. Form fields without an associated label
  const labelledIds = new Set();
  document.querySelectorAll("label[for]").forEach((l) => labelledIds.add(l.getAttribute("for")));
  let unlabelled = [];
  document.querySelectorAll("input, textarea, select").forEach((field) => {
    const type = (field.getAttribute("type") || "").toLowerCase();
    if (["hidden", "submit", "button", "image", "reset"].includes(type)) return;
    if (!isVisible(field)) return;
    const id = field.getAttribute("id");
    const hasLabel =
      (id && labelledIds.has(id)) ||
      (field.getAttribute("aria-label") || "").trim() ||
      (field.getAttribute("aria-labelledby") || "").trim() ||
      field.closest("label") !== null;
    if (!hasLabel) unlabelled.push(field);
  });
  if (unlabelled.length) push("1.3.1 Info and Relationships", "Form field has no associated <label>, aria-label, or aria-labelledby", "Serious", unlabelled[0], unlabelled.length);

  // 6. Duplicate id attributes
  const idCounts = {};
  document.querySelectorAll("[id]").forEach((el) => {
    const id = el.getAttribute("id");
    if (!id) return;
    (idCounts[id] = idCounts[id] || []).push(el);
  });
  const dupIds = Object.entries(idCounts).filter(([, els]) => els.length > 1);
  if (dupIds.length) push("4.1.1 Parsing", `Duplicate id attribute used more than once (${dupIds.length} distinct id(s) affected)`, "Moderate", dupIds[0][1][0], dupIds.reduce((s, [, els]) => s + els.length, 0));

  // 7. Heading hierarchy skips + 8/9. h1 presence
  const headings = Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, h6"));
  let prevLevel = null;
  let skips = [];
  headings.forEach((h) => {
    const level = parseInt(h.tagName[1], 10);
    if (prevLevel !== null && level > prevLevel + 1) skips.push(h);
    prevLevel = level;
  });
  if (skips.length) push("1.3.1 Info and Relationships", `Heading level skips a level (e.g. <h1> straight to <h3>) at ${skips.length} point(s)`, "Minor", skips[0], skips.length);

  const h1s = document.querySelectorAll("h1");
  if (h1s.length === 0) push("2.4.6 Headings and Labels", "Page has no <h1> heading", "Moderate", null, 1);
  else if (h1s.length > 1) push("2.4.6 Headings and Labels", `Page has ${h1s.length} <h1> headings - should generally be exactly one`, "Minor", h1s[1], h1s.length);

  // 10. Generic/ambiguous link text
  const genericTexts = new Set(["click here", "here", "read more", "more", "learn more", "link", "this link", "more info"]);
  let genericLinks = [];
  document.querySelectorAll("a[href]").forEach((a) => {
    const text = (a.textContent || "").trim().toLowerCase();
    if (genericTexts.has(text)) genericLinks.push(a);
  });
  if (genericLinks.length) push("2.4.4 Link Purpose (In Context)", `Link text like "click here" or "read more" doesn't describe its destination out of context`, "Minor", genericLinks[0], genericLinks.length);

  // 11. Positive tabindex (breaks natural tab order)
  let positiveTabindex = [];
  document.querySelectorAll("[tabindex]").forEach((el) => {
    const v = parseInt(el.getAttribute("tabindex"), 10);
    if (!isNaN(v) && v > 0) positiveTabindex.push(el);
  });
  if (positiveTabindex.length) push("2.4.3 Focus Order", "Positive tabindex value overrides natural tab order, which usually breaks keyboard navigation", "Moderate", positiveTabindex[0], positiveTabindex.length);

  // 12. Skip-to-content link as (one of) the first focusable elements
  const bodyLinks = Array.from(document.querySelectorAll("a[href]")).slice(0, 5);
  const hasSkipLink = bodyLinks.some((a) => /skip to|skip navigation|skip to content|skip to main/i.test(a.textContent || ""));
  if (!hasSkipLink && bodyLinks.length > 0) push("2.4.1 Bypass Blocks", "No 'skip to content' link found among the first links on the page - keyboard users must tab through the whole nav on every page", "Minor", null, 1);

  // 13. Video/audio without a captions track
  let uncaptioned = [];
  document.querySelectorAll("video, audio").forEach((media) => {
    const hasCaptionTrack = Array.from(media.querySelectorAll("track")).some((t) => (t.getAttribute("kind") || "").toLowerCase() === "captions");
    if (!hasCaptionTrack) uncaptioned.push(media);
  });
  if (uncaptioned.length) push("1.2.2 Captions (Prerecorded)", "<video>/<audio> element has no <track kind='captions'> child", "Serious", uncaptioned[0], uncaptioned.length);

  // 14. iframe missing title
  let untitledFrames = [];
  document.querySelectorAll("iframe").forEach((f) => {
    if (!(f.getAttribute("title") || "").trim()) untitledFrames.push(f);
  });
  if (untitledFrames.length) push("4.1.2 Name, Role, Value", "<iframe> missing a title attribute describing its content", "Moderate", untitledFrames[0], untitledFrames.length);

  // 15. Viewport meta blocking zoom
  const viewport = document.querySelector('meta[name="viewport"]');
  if (viewport) {
    const content = (viewport.getAttribute("content") || "").toLowerCase();
    const blocksZoom = /user-scalable\s*=\s*no/.test(content) || /maximum-scale\s*=\s*(0(\.\d+)?|1(\.0*)?)(?!\d)/.test(content);
    if (blocksZoom) push("1.4.4 Resize Text", "Viewport meta tag disables or caps pinch-zoom (user-scalable=no or maximum-scale<=1), preventing low-vision users from zooming in", "Serious", viewport, 1);
  }

  // 16. Color contrast - real WCAG relative-luminance/contrast-ratio math
  // (W3C's published formula, not a third-party library), run against
  // actual computed styles. Bounded scan (first ~600 candidate elements,
  // first 25 failures kept) to stay fast on large pages.
  const parseColor = (str) => {
    const m = (str || "").match(/rgba?\(([^)]+)\)/);
    if (!m) return [255, 255, 255, 1];
    const parts = m[1].split(",").map((s) => parseFloat(s.trim()));
    return [parts[0] || 0, parts[1] || 0, parts[2] || 0, parts.length > 3 ? parts[3] : 1];
  };
  const relLuminance = ([r, g, b]) => {
    const toLin = (c) => {
      c /= 255;
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * toLin(r) + 0.7152 * toLin(g) + 0.0722 * toLin(b);
  };
  const contrastRatio = (rgb1, rgb2) => {
    const L1 = relLuminance(rgb1);
    const L2 = relLuminance(rgb2);
    const lighter = Math.max(L1, L2);
    const darker = Math.min(L1, L2);
    return (lighter + 0.05) / (darker + 0.05);
  };
  const effectiveBackground = (el) => {
    let node = el;
    while (node && node !== document.documentElement) {
      const bg = parseColor(getComputedStyle(node).backgroundColor);
      if (bg[3] > 0.05) {
        if (bg[3] < 1) {
          return [bg[0] * bg[3] + 255 * (1 - bg[3]), bg[1] * bg[3] + 255 * (1 - bg[3]), bg[2] * bg[3] + 255 * (1 - bg[3])];
        }
        return [bg[0], bg[1], bg[2]];
      }
      node = node.parentElement;
    }
    return [255, 255, 255];
  };

  const contrastFailures = [];
  const seenKeys = new Set();
  const candidates = document.querySelectorAll("body *");
  let scanned = 0;
  for (const el of candidates) {
    if (scanned >= 600 || contrastFailures.length >= 25) break;
    let hasDirectText = false;
    for (const child of el.childNodes) {
      if (child.nodeType === 3 && child.textContent.trim().length > 0) {
        hasDirectText = true;
        break;
      }
    }
    if (!hasDirectText) continue;
    scanned += 1;
    if (!isVisible(el)) continue;
    const style = getComputedStyle(el);
    const fg = parseColor(style.color);
    if (fg[3] < 0.2) continue;
    const bg = effectiveBackground(el);
    const ratio = contrastRatio([fg[0], fg[1], fg[2]], bg);
    const fontSize = parseFloat(style.fontSize) || 16;
    const fontWeight = parseInt(style.fontWeight, 10) || 400;
    const isLarge = fontSize >= 24 || (fontSize >= 18.66 && fontWeight >= 700);
    const threshold = isLarge ? 3.0 : 4.5;
    if (ratio < threshold) {
      const key = style.color + "|" + JSON.stringify(bg.map(Math.round)) + "|" + el.tagName;
      if (seenKeys.has(key)) continue;
      seenKeys.add(key);
      contrastFailures.push({ el, ratio: Math.round(ratio * 100) / 100, threshold });
    }
  }
  if (contrastFailures.length) {
    const worst = contrastFailures.reduce((a, b) => (a.ratio < b.ratio ? a : b));
    push(
      "1.4.3 Contrast (Minimum)",
      `Text color contrast below WCAG AA (needs ${worst.threshold}:1, worst found was ${worst.ratio}:1) on ${contrastFailures.length} element(s)`,
      "Serious",
      worst.el,
      contrastFailures.length
    );
  }

  return issues;
}
"""

_CUSTOM_RULESET_NOTE = (
    "Runs a ~16-rule custom ruleset (incl. a real WCAG contrast-ratio scan) rather than axe-core, "
    "because axe.min.js hasn't been supplied yet. Drop it at "
    "app/topic1_website_auditor/vendor/axe.min.js and the next audit will use the real axe-core "
    "engine automatically - no code changes needed."
)


def _run_wcag_checks_sync(url: str) -> Dict[str, Any]:
    from playwright.sync_api import sync_playwright

    use_axe = _VENDOR_AXE_PATH.exists()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"] + LOW_MEMORY_CHROMIUM_ARGS,
        )
        context = browser.new_context(
            viewport={"width": 1366, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        page.set_default_timeout(12000)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(1200)
            _dismiss_cookie_banner(page)
            page.wait_for_timeout(400)

            if use_axe:
                try:
                    page.add_script_tag(path=str(_VENDOR_AXE_PATH))
                    axe_output = page.evaluate(
                        "async () => { return await axe.run(document, { resultTypes: ['violations'] }); }"
                    )
                    version = page.evaluate("() => (window.axe && window.axe.version) || 'unknown'")
                    return {
                        "raw_issues": _axe_violations_to_issues(axe_output.get("violations", [])),
                        "engine": f"axe-core {version}",
                        "engine_note": (
                            f"Ran using axe-core {version}, the same open-source engine behind Chrome "
                            "DevTools' Accessibility panel and Lighthouse's accessibility score."
                        ),
                    }
                except Exception:
                    # axe.min.js present but failed to load/run (corrupt file,
                    # page CSP blocking injected scripts, etc.) - fall back to
                    # the custom ruleset below rather than losing the check
                    # entirely.
                    pass

            raw_issues = page.evaluate(_CHECK_SCRIPT)
            return {
                "raw_issues": raw_issues or [],
                "engine": "custom-ruleset",
                "engine_note": _CUSTOM_RULESET_NOTE,
            }
        finally:
            browser.close()


def _build_result(
    url: str,
    raw_issues: List[Dict[str, Any]],
    engine: str = "custom-ruleset",
    engine_note: Optional[str] = None,
) -> WCAGAuditResult:
    issues = [
        WCAGIssue(
            code=i.get("code", "unknown"),
            description=i.get("description", "Accessibility issue"),
            impact=i.get("impact", "Moderate"),
            element=i.get("element"),
            occurrences=i.get("occurrences", 1),
        )
        for i in raw_issues
    ]
    total_occurrences = sum(i.occurrences for i in issues)
    deduction = sum(_SEVERITY_WEIGHT.get(i.impact.lower(), 3) for i in issues)
    score = max(0, 100 - deduction)

    return WCAGAuditResult(
        url=url,
        score=score,
        total_issues=len(issues),
        total_occurrences=total_occurrences,
        issues=issues,
        engine=engine,
        engine_note=engine_note,
    )


async def fetch_and_audit_wcag(url: str) -> WCAGAuditResult:
    # Only one Chromium-based check runs at a time - see app/common/browser_lock.py
    async with CHROMIUM_SLOT:
        result = await asyncio.to_thread(_run_wcag_checks_sync, url)
    return _build_result(
        url,
        result["raw_issues"],
        engine=result["engine"],
        engine_note=result["engine_note"],
    )
