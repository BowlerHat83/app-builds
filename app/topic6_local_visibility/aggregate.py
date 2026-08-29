import os
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.common.audit_helpers import envelope, normalize_url, safe_check
from app.topic6_local_visibility.services.gbp_review_service import GBPReviewService
from app.topic6_local_visibility.services.local_service import LocalVisibilityService
from app.topic6_local_visibility.services.screenshot_service import GBPScreenshotService
from app.topic6_local_visibility.services.url_extractor_service import URLExtractorService

router = APIRouter()

local_svc = LocalVisibilityService()
review_svc = GBPReviewService()
screenshot_svc = GBPScreenshotService()
extractor_svc = URLExtractorService()


async def run_full_audit(
    business_name: Optional[str] = None,
    target_location: Optional[str] = None,
    target_url: Optional[str] = None,
    brightlocal_bytes: Optional[bytes] = None,
    extra_keywords: Optional[list] = None,
    prewarm_job: Optional[dict] = None,
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
    """
    warnings: list = []
    api_key = os.environ.get("SERPAPI_KEY")

    if (not business_name or not target_location) and target_url:
        inferred, infer_warn = await safe_check(
            extractor_svc.extract_business_info(normalize_url(target_url)), "Business info auto-detect", timeout=15
        )
        if infer_warn:
            warnings.append(infer_warn)
        if inferred:
            business_name = business_name or inferred.get("business_name")
            target_location = target_location or inferred.get("location")

    if not business_name or not target_location:
        return envelope(
            "Topic 6: Local Visibility Audit",
            {},
            warnings + ["business_name and target_location are required (or supply target_url so they can be auto-detected)."],
        )

    keywords = [business_name, f"{business_name} {target_location}"]
    # extra_keywords are the top unbranded keywords sourced from Topic 3
    # (organic), Topic 4 (AI visibility) and Topic 5 (PPC) - see
    # _extract_unbranded_keywords in routes/master_audit.py. Testing map-pack
    # rank against these too (not just business-name variants, which almost
    # always already rank) shows whether the business actually shows up in
    # the map pack for what people searching the category tend to type.
    if extra_keywords:
        for kw in extra_keywords:
            if kw and kw not in keywords:
                keywords.append(kw)

    citations = None
    if brightlocal_bytes:
        citations, citations_warn = await safe_check(
            local_svc.process_brightlocal_csv(brightlocal_bytes), "BrightLocal CSV parse", timeout=15
        )
        if citations_warn:
            warnings.append(citations_warn)
    else:
        warnings.append("No BrightLocal CSV uploaded - citation/NAP metrics unavailable.")

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
    screenshot_awaitable = (prewarm_job or {}).get("screenshot_task") or screenshot_svc.capture_screenshot(
        business_name, target_location
    )
    screenshot, screenshot_warn = await safe_check(screenshot_awaitable, "GBP screenshot capture", timeout=130)
    if screenshot_warn:
        warnings.append(screenshot_warn)

    if not api_key:
        warnings.append("SERPAPI_KEY not configured - map-pack rank and review data are unavailable rather than estimated.")

    data = {
        "topic": "Topic 6: Local Visibility Audit",
        "business_name": business_name,
        "location": target_location,
        "citations": citations,
        "map_pack": map_pack,
        "reviews": reviews,
        "profile_screenshot": screenshot,
    }

    return envelope("Topic 6: Local Visibility Audit", data, warnings)


@router.post("/audit-all", summary="Run Topic 6 Audit")
async def run_audit_all(
    business_name: Optional[str] = Form(None),
    target_location: Optional[str] = Form(None),
    target_url: Optional[str] = Form(None),
    brightlocal_csv: Optional[UploadFile] = File(None),
):
    return await run_full_audit(
        business_name=business_name,
        target_location=target_location,
        target_url=target_url,
        brightlocal_bytes=await brightlocal_csv.read() if brightlocal_csv else None,
    )
