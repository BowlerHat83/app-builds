import os
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.common.audit_helpers import envelope, normalize_url, safe_check, source, extra
from app.topic6_local_visibility.services.gbp_review_service import GBPReviewService
from app.topic6_local_visibility.services.local_service import LocalVisibilityService
from app.topic6_local_visibility.services.screenshot_service import GBPScreenshotService
from app.topic6_local_visibility.services.url_extractor_service import URLExtractorService
from app.common.integrations.brightlocal import fetch_citation_tracker_csv

router = APIRouter()

local_svc = LocalVisibilityService()
review_svc = GBPReviewService()
screenshot_svc = GBPScreenshotService()
extractor_svc = URLExtractorService()


# Local-intent phrasings a prospective customer actually types into Google
# when searching for a category of business - built from a plain "what do
# you sell" term (core_offering, e.g. "kitchen showroom") rather than the
# business name. A branded query like "Bowler Hat Manchester" is nearly
# guaranteed to already rank #1 in the map pack, so folding it into the
# average told you almost nothing about real local visibility and skewed
# the score toward looking better than it actually is.
#
# Deliberately template-based rather than calling out to an LLM for
# synonyms: fully deterministic, no new external dependency/cost/failure
# mode on top of everything already stabilized this session, and every
# variation stays anchored to the exact phrase supplied - it can't drift
# into a different service the way an automatically generated synonym
# occasionally could. local_service.fetch_map_pack_position appends
# target_location onto every keyword itself when building the live SerpApi
# query, so location is deliberately left out of these templates - it's
# the "then add a location" step, just handled one layer down instead of
# baked into the text here (baking it in here too would send Google a
# double-location query like "kitchen showroom Manchester Manchester").
_OFFERING_KEYWORD_TEMPLATES = [
    "{offering}",
    "best {offering}",
    "{offering} near me",
    "{offering} company",
    "{offering} services",
    "local {offering}",
    "{offering_plural}",
    "{offering} specialists",
]


def _pluralize(term: str) -> str:
    """Naive last-word pluralization ("kitchen showroom" -> "kitchen showrooms").
    Good enough for a keyword variation, not meant to be linguistically exact."""
    return term if term.endswith("s") else f"{term}s"


def _has_adjacent_duplicate_word(phrase: str) -> bool:
    """Catches the awkward case where the offering itself already ends in a
    word a template also appends - e.g. core_offering="roofing services"
    plus the "{offering} services" template would otherwise produce
    "roofing services services"."""
    words = phrase.lower().split()
    return any(a == b for a, b in zip(words, words[1:]))


def generate_offering_keywords(core_offering: str, max_count: int = 8) -> list:
    """
    Builds up to max_count template-based variations from a plain
    core-offering phrase - see _OFFERING_KEYWORD_TEMPLATES above for why
    this is template-based rather than branded terms or LLM-generated
    synonyms. Deduplicates case-insensitively (e.g. an offering that
    already ends in "s" makes the plural template identical to the base
    one) and drops any candidate with an awkward repeated word.
    """
    offering = " ".join(core_offering.strip().split())
    if not offering:
        return []

    candidates = [
        template.format(offering=offering, offering_plural=_pluralize(offering))
        for template in _OFFERING_KEYWORD_TEMPLATES
    ]

    seen = set()
    keywords = []
    for kw in candidates:
        key = kw.lower()
        if key in seen or _has_adjacent_duplicate_word(kw):
            continue
        seen.add(key)
        keywords.append(kw)
        if len(keywords) >= max_count:
            break
    return keywords


# Common words too generic to count as a topical match on their own (a
# core offering of "digital marketing services" shouldn't treat every
# organic keyword containing "services" as related). Deliberately short -
# this only needs to filter out connective/filler words, not build a real
# stopword list.
_STOPWORDS = {"a", "an", "the", "and", "or", "for", "of", "in", "on", "to", "with", "near", "me", "services", "service"}


def _significant_words(phrase: str) -> set:
    return {w for w in phrase.lower().split() if w not in _STOPWORDS and len(w) > 2}


def select_real_offering_keywords(
    organic_top_keywords: Optional[list], core_offering: str, business_name: Optional[str], limit: int = 3
) -> list:
    """
    Pulls the top real, already-uploaded Ahrefs organic keywords (real
    search demand, not fabricated) that are both unbranded and topically
    related to the core offering - walking organic_top_keywords in the
    order Topic 3 already ranked them (by estimated traffic, then volume -
    see top_keywords_service.py), so "top 3" means the highest-value real
    matches, not just the first 3 in the file.

    This is also how real geographic breadth gets in: if the business
    already ranks organically for a hyper-local suburb query, a city-wide
    one, and a wider-region one, all three can surface here exactly as
    real search data shows them - genuinely at whatever scale people are
    searching, rather than guessed neighbourhood/region names templated in
    with no evidence they're real search terms.
    """
    offering_words = _significant_words(core_offering)
    if not offering_words:
        return []
    business_lower = (business_name or "").strip().lower()

    picked: list = []
    for row in organic_top_keywords or []:
        if len(picked) >= limit:
            break
        kw = str((row or {}).get("keyword", "")).strip()
        if not kw:
            continue
        kw_lower = kw.lower()
        if business_lower and business_lower in kw_lower:
            continue  # still branded - excluded same as everywhere else in this check
        if not (_significant_words(kw) & offering_words):
            continue  # not topically related enough to the core offering
        if kw not in picked:
            picked.append(kw)
    return picked


def build_topic6_keywords(
    core_offering: str,
    business_name: Optional[str],
    organic_top_keywords: Optional[list],
    target_count: int = 8,
    max_real: int = 3,
) -> list:
    """
    Combines up to max_real real, topically-relevant organic keywords
    (select_real_offering_keywords - prioritized first, since real search
    data beats a guess) with deterministic template variations
    (generate_offering_keywords) as the floor/fallback, up to target_count
    total. The bare core-offering template is always included unless
    target_count is smaller than max_real + 1, which it never is at the
    defaults - so there's always at least one deterministic city-tier
    check even when no Ahrefs CSV was uploaded for this run.
    """
    real_keywords = select_real_offering_keywords(organic_top_keywords, core_offering, business_name, limit=max_real)
    templates = generate_offering_keywords(core_offering, max_count=8)

    seen = set()
    keywords: list = []
    for kw in real_keywords + templates:
        key = kw.lower()
        if key in seen:
            continue
        seen.add(key)
        keywords.append(kw)
        if len(keywords) >= target_count:
            break
    return keywords


def _audit_inputs(business_name, target_location, core_offering, input_sources: dict) -> list:
    """The three inputs Topic 6 actually ran with, and where each came from - shown at the top of the Topic 6 tab."""
    rows = []
    for key, label, value in (
        ("business_name", "Business name", business_name),
        ("target_location", "Location", target_location),
        ("core_offering", "Core offering", core_offering),
    ):
        rows.append({
            "key": key,
            "label": label,
            "value": value or None,
            "source": input_sources.get(key) or ("Entered manually" if value else "Not found"),
        })
    return rows


async def run_full_audit(
    business_name: Optional[str] = None,
    target_location: Optional[str] = None,
    target_url: Optional[str] = None,
    brightlocal_bytes: Optional[bytes] = None,
    extra_keywords: Optional[list] = None,
    core_offering: Optional[str] = None,
    organic_keywords: Optional[list] = None,
    prewarm_job: Optional[dict] = None,
    enable_screenshot: bool = False,
    input_sources: Optional[dict] = None,
    **_ignored,
) -> dict:
    """
    Topic 6: Local Visibility.

    Map-pack rank and reviews are only ever real (SerpApi, via SERPAPI_KEY)
    or explicitly marked unavailable - never a fabricated number or someone
    else's testimonials dressed up as this client's reviews, which is what
    this topic used to silently return.

    prewarm_job, if provided, is a dict from app/common/prewarm_jobs.py -
    when its screenshot_task was already kicked off during the intake
    flow's first screen (only possible if business_name/target_location
    were both supplied there), this awaits that instead of launching a
    fresh capture.

    enable_screenshot defaults to False - the GBP screenshot launches a
    real, un-resource-blocked Chromium instance (deliberately, for visual
    fidelity) and was a live OOM-crash suspect earlier this session, just a
    lower-probability one than Topic 7's crawl since it's a single page
    load rather than up to 30. Rather than silently accept that risk on
    every run, it's now opt-in per audit (see the checkbox on the intake
    screen / enable_topic6_screenshot in audit_jobs.py) - the reader
    explicitly chooses to spend the memory budget on it for a given run.
    """
    warnings: list = []
    input_sources = dict(input_sources or {})

    # Topic 6 only runs at all when a BrightLocal Citation Tracker CSV was
    # uploaded - previously map-pack rank, reviews, and the GBP screenshot
    # all ran off live SerpApi/Chromium calls regardless, with citations
    # alone silently coming back None. That spent real API/Chromium budget
    # on a topic whose input wasn't actually supplied for this run.
    #
    # No CSV uploaded? Try the BrightLocal API before giving up (only does
    # anything when BRIGHTLOCAL_API_KEY is set - see
    # app/common/integrations/brightlocal.py). An uploaded CSV always wins.
    sources, extras = [], []
    if brightlocal_bytes:
        sources.append(source("BrightLocal Citation Tracker CSV", "csv", "Uploaded export - citations, NAP accuracy, opportunities."))
    else:
        brightlocal_bytes, bl_note = await fetch_citation_tracker_csv(
            business_name=business_name, target_url=target_url, target_location=target_location
        )
        if brightlocal_bytes:
            sources.append(source("BrightLocal Citation Tracker (API)", "api", bl_note or "Pulled from BrightLocal."))

    if not brightlocal_bytes:
        extras.append(extra(
            "BrightLocal Citation Tracker", "missing",
            (bl_note + " " if bl_note else "")
            + "Topic 6 runs once citation data is available - upload the Citation Tracker CSV, or set up a "
            "Citation Tracker report for this business in BrightLocal.",
        ))
        return envelope("Topic 6: Local Visibility Audit", {}, warnings, sources=sources, extras=extras)

    api_key = os.environ.get("SERPAPI_KEY")

    if (not business_name or not target_location) and target_url:
        inferred, infer_warn = await safe_check(
            extractor_svc.extract_business_info(normalize_url(target_url)), "Business info auto-detect", timeout=15
        )
        if infer_warn:
            warnings.append(infer_warn)
        if inferred:
            if not business_name and inferred.get("business_name"):
                business_name = inferred["business_name"]
                input_sources["business_name"] = "Auto-detected from website (during the audit)"
            if not target_location and inferred.get("location"):
                target_location = inferred["location"]
                input_sources["target_location"] = "Auto-detected from website (during the audit)"

    if not business_name or not target_location:
        extras.append(extra("Business name & location", "missing", "Needed for map-pack rank and reviews (couldn't auto-detect them from the site)."))
        return envelope("Topic 6: Local Visibility Audit", {}, warnings, sources=sources, extras=extras)

    if core_offering:
        # Core-offering-based keywords only - the business name alone and
        # "business name + location" are deliberately excluded from this
        # check entirely now. Real, topically-relevant organic keywords
        # (from the already-uploaded Ahrefs export, if any) are prioritized
        # over the deterministic templates - see build_topic6_keywords
        # above for why, including how this is what surfaces real
        # local/city/region-scale variety when it exists.
        keywords = build_topic6_keywords(core_offering, business_name, organic_keywords)
        extras.append(extra("Core Offering", "included", f"Map-pack keywords built around '{core_offering}'."))
        if organic_keywords:
            extras.append(extra("Real search terms for map-pack check", "included", "Topic 6 keywords include real organic keywords from Ahrefs."))
        else:
            extras.append(extra(
                "Real search terms for map-pack check", "missing",
                "No Ahrefs organic keywords this run, so map-pack keywords are wording variations of the Core Offering only.",
            ))
    else:
        # No Core Offering supplied for this run - fall back to the old
        # branded-seed behaviour (still real data, just skewed toward
        # queries that are nearly guaranteed to already rank) rather than
        # returning no map-pack data at all.
        keywords = [business_name, f"{business_name} {target_location}"]
        # extra_keywords are the top unbranded keywords sourced from Topic 3
        # (organic), Topic 4 (AI visibility) and Topic 5 (PPC) - see
        # _extract_unbranded_keywords in routes/master_audit.py.
        if extra_keywords:
            for kw in extra_keywords:
                if kw and kw not in keywords:
                    keywords.append(kw)
        extras.append(extra(
            "Core Offering", "missing",
            "Map-pack rank was tested against the business name, which almost always ranks - add a Core Offering "
            "(e.g. 'kitchen showroom') on the intake screen for a more representative result.",
        ))

    citations = None
    if brightlocal_bytes:
        citations, citations_warn = await safe_check(
            local_svc.process_brightlocal_csv(brightlocal_bytes), "BrightLocal CSV parse", timeout=15
        )
        if citations_warn:
            warnings.append(citations_warn)

    # fetch_map_pack_position now runs its keyword lookups concurrently
    # instead of one at a time (see local_service.py) - this was timing out
    # at the old 20s budget with 20s being spent on requests running
    # sequentially. 30s stays as headroom for SerpApi being slow, not as a
    # crutch for sequential requests anymore.
    map_pack, map_pack_warn = await safe_check(
        local_svc.fetch_map_pack_position(business_name, target_location, keywords, api_key=api_key),
        "Map-pack rank check", timeout=30,
    )
    if map_pack_warn:
        warnings.append(map_pack_warn)

    # Reviews are resolved independently (engine=google_maps -> data_id ->
    # google_maps_reviews) inside gbp_review_service.py, rather than reusing
    # anything from the map-pack check above - that check's google_local
    # "place_id" turned out to be a raw CID incompatible with the reviews
    # endpoint (confirmed via a live diagnostic against this exact business).
    reviews, reviews_warn = await safe_check(
        review_svc.get_reviews(business_name, target_location, api_key=api_key),
        "GBP reviews lookup", timeout=20,
    )
    if reviews_warn:
        warnings.append(reviews_warn)

    # Same single-slot Chromium semaphore as Topic 1's WCAG/GDPR checks and
    # Topic 7's form crawl (see app/common/browser_lock.py) - only one
    # headless browser runs at a time across the whole audit. Topic 1's own
    # checks were already bumped to 90s each and Topic 7's crawl to 100s for
    # exactly this reason (see the comment in topic1's aggregate.py), but
    # this one was left at 45s - meaning it could time out purely from
    # queueing behind those two, before the actual (much shorter) screenshot
    # capture ever got a turn at the browser. 130s gives room to wait out a
    # worst-case queue behind Topic 7's crawl and still complete; a normal
    # capture (a few seconds once it has the browser) finishes just as fast
    # as before.
    screenshot = None
    if enable_screenshot:
        screenshot_awaitable = (prewarm_job or {}).get("screenshot_task") or screenshot_svc.capture_screenshot(
            business_name, target_location
        )
        screenshot, screenshot_warn = await safe_check(screenshot_awaitable, "GBP screenshot capture", timeout=130)
        if screenshot_warn:
            warnings.append(screenshot_warn)
        if screenshot and screenshot.get("status") != "captured":
            screenshot = None
    if enable_screenshot:
        extras.append(extra("Google Business Profile screenshot", "included" if screenshot else "unavailable",
                            "Captured live." if screenshot else "Enabled, but the capture didn't complete this run."))
    else:
        extras.append(extra("Google Business Profile screenshot", "off", "Opt-in on the intake screen."))

    if api_key:
        sources.append(source("SerpApi (Google Maps)", "api", f"Live map-pack rank across {len(keywords)} keywords, plus Google reviews."))
    else:
        extras.append(extra("Map-pack rank & reviews", "unavailable", "SerpApi key not configured on the server."))

    data = {
        "topic": "Topic 6: Local Visibility Audit",
        "audit_inputs": _audit_inputs(business_name, target_location, core_offering, input_sources),
        "business_name": business_name,
        "location": target_location,
        "core_offering": core_offering,
        "citations": citations,
        "map_pack": map_pack,
        "reviews": reviews,
        "profile_screenshot": screenshot,
    }

    return envelope("Topic 6: Local Visibility Audit", data, warnings, sources=sources, extras=extras)


@router.post("/audit-all", summary="Run Topic 6 Audit")
async def run_audit_all(
    business_name: Optional[str] = Form(None),
    target_location: Optional[str] = Form(None),
    target_url: Optional[str] = Form(None),
    core_offering: Optional[str] = Form(None, description="What the business sells, e.g. 'kitchen showroom' - drives the map-pack keyword set"),
    brightlocal_csv: Optional[UploadFile] = File(None),
    enable_screenshot: bool = Form(False),
):
    return await run_full_audit(
        business_name=business_name,
        target_location=target_location,
        target_url=target_url,
        core_offering=core_offering,
        brightlocal_bytes=await brightlocal_csv.read() if brightlocal_csv else None,
        enable_screenshot=enable_screenshot,
    )
