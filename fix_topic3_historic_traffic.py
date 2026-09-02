import pathlib

path = pathlib.Path.home() / "app-builds" / "app" / "topic3_ahrefs_auditor" / "services" / "historic_traffic_service.py"
text = path.read_text(encoding="utf-8")

old_detect = '''    curr_traffic_col = next((c for c in df.columns if "current" in c and "traffic" in c), None)
    prev_traffic_col = next((c for c in df.columns if "previous" in c and "traffic" in c), None)

    # This used to silently fall back to specific hardcoded numbers (218 /
    # 255) whenever the expected traffic columns weren't found in the CSV -
    # a fabricated result that looks like real data, not a missing one.
    # Raising here instead lets the caller (aggregate.py's _try) turn this
    # into an honest warning and a null block, the same way every other
    # missing-column case in this codebase is handled.
    if not curr_traffic_col or not prev_traffic_col:
        raise ValueError(
            f"CSV missing expected 'Current Traffic'/'Previous Traffic' columns. Found: {list(df.columns)}"
        )

    current_traffic = int(pd.to_numeric(df[curr_traffic_col], errors="coerce").fillna(0).sum())
    previous_traffic = int(pd.to_numeric(df[prev_traffic_col], errors="coerce").fillna(0).sum())'''

new_detect = '''    curr_traffic_col = next((c for c in df.columns if "current" in c and "traffic" in c), None)
    prev_traffic_col = next((c for c in df.columns if "previous" in c and "traffic" in c), None)

    # A plain (non date-compared) Ahrefs Organic Keywords export never has
    # Current/Previous Traffic columns at all - those only appear when the
    # export was generated with a comparison date range. This methodology
    # only ever needed a single current-traffic baseline (see the modeled
    # curve below), so fall back to the export's plain "Organic traffic"
    # column - present on every export - instead of requiring a comparison
    # that was never actually necessary. This used to silently fall back to
    # hardcoded numbers (218 / 255) when no traffic column was found at all
    # - that's still an honest error, not modeled data.
    organic_traffic_col = next((c for c in df.columns if c == "organic_traffic"), None)

    if curr_traffic_col:
        current_traffic = int(pd.to_numeric(df[curr_traffic_col], errors="coerce").fillna(0).sum())
    elif organic_traffic_col:
        current_traffic = int(pd.to_numeric(df[organic_traffic_col], errors="coerce").fillna(0).sum())
    else:
        raise ValueError(
            f"CSV missing a traffic column to model from (looked for 'Current Traffic' or 'Organic traffic'). Found: {list(df.columns)}"
        )

    previous_traffic = (
        int(pd.to_numeric(df[prev_traffic_col], errors="coerce").fillna(0).sum()) if prev_traffic_col else None
    )'''

old_return = '''        "previous_month_traffic": previous_traffic,
        "traffic_change_mom": current_traffic - previous_traffic,'''

new_return = '''        "previous_month_traffic": previous_traffic,
        "traffic_change_mom": (current_traffic - previous_traffic) if previous_traffic is not None else None,'''

for old, new, name in [(old_detect, new_detect, "detection block"), (old_return, new_return, "return dict")]:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly 1 match for {name}, found {count}. Aborting - file may have changed.")
    text = text.replace(old, new)

path.write_text(text, encoding="utf-8")
print("Patched historic_traffic_service.py (2 edits applied).")
