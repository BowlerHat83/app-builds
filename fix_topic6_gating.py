import pathlib

path = pathlib.Path.home() / "app-builds" / "app" / "topic6_local_visibility" / "aggregate.py"
text = path.read_text(encoding="utf-8")

old = '''    warnings: list = []
    api_key = os.environ.get("SERPAPI_KEY")'''

new = '''    warnings: list = []

    # Topic 6 only runs at all when a BrightLocal Citation Tracker CSV was
    # uploaded - previously map-pack rank, reviews, and the GBP screenshot
    # all ran off live SerpApi/Chromium calls regardless, with citations
    # alone silently coming back None. That spent real API/Chromium budget
    # on a topic whose input wasn't actually supplied for this run.
    if not brightlocal_bytes:
        return envelope(
            "Topic 6: Local Visibility Audit",
            {},
            [
                "No BrightLocal Citation Tracker CSV was uploaded - Topic 6 only runs when this input is "
                "provided. Upload one to get citation data, map-pack rank, reviews, and the optional GBP "
                "screenshot for this run."
            ],
        )

    api_key = os.environ.get("SERPAPI_KEY")'''

count = text.count(old)
if count != 1:
    raise SystemExit(f"Expected exactly 1 match, found {count}. Aborting - file may have changed.")

path.write_text(text.replace(old, new), encoding="utf-8")
print(f"Patched {path} ({count} match replaced).")
