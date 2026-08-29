import csv
import io
import re
from typing import Dict, Any, Optional
import urllib.request
from bs4 import BeautifulSoup

class ThinContentService:
    async def analyze_thin_content(
        self, 
        target_url: str, 
        csv_bytes: Optional[bytes] = None, 
        word_threshold: int = 300,
        char_threshold: int = 1500
    ) -> Dict[str, Any]:
        results = []
        thin_count = 0
        pages_missing_word_count = 0

        # Option A: Parse Screaming Frog / Ahrefs CSV directly
        if csv_bytes:
            try:
                decoded = csv_bytes.decode('utf-8-sig', errors='ignore')
                reader = csv.DictReader(io.StringIO(decoded))
                
                for row in reader:
                    # Match Screaming Frog 'Address' or generic URL headers
                    url = row.get('Address') or row.get('URL') or row.get('Target URL') or row.get('Top page')
                    if not url or not url.startswith('http'):
                        continue

                    # Filter out non-200 or non-indexable pages if Screaming Frog data exists
                    status_code = row.get('Status Code', '200')
                    indexability = row.get('Indexability', 'Indexable')
                    if status_code != '200' or indexability == 'Non-Indexable':
                        continue

                    # Extract Word Count if provided directly by Screaming Frog.
                    # Screaming Frog's default "Internal HTML" export doesn't
                    # include Word Count unless content extraction is
                    # separately enabled in the crawl config - a genuinely
                    # common export shape. This used to treat a missing
                    # column as "0 words, definitely thin" for every single
                    # row, which could report 100% thin content with no
                    # warning at all. A page this code never actually
                    # measured is unknown, not thin - it's excluded from the
                    # count/percentage below instead, and pages_missing_word_
                    # count says how many were skipped for this reason.
                    sf_word_count = row.get('Word Count')
                    if sf_word_count is not None and sf_word_count.isdigit():
                        w_count = int(sf_word_count)
                        c_count = w_count * 6  # Estimate char count from word count
                        is_thin = w_count < word_threshold
                    else:
                        pages_missing_word_count += 1
                        continue

                    if is_thin:
                        thin_count += 1

                    results.append({
                        "url": url,
                        "character_count": c_count,
                        "word_count": w_count,
                        "is_thin": is_thin
                    })

                total_rows_seen = len(results) + pages_missing_word_count
                if total_rows_seen:
                    note = None
                    if pages_missing_word_count:
                        note = (
                            f"{pages_missing_word_count} of {total_rows_seen} pages in this export don't have a "
                            "Word Count value (Screaming Frog only includes this when content extraction is "
                            "enabled in the crawl) and were excluded from this analysis rather than assumed thin."
                        )
                    if not results:
                        # Every row lacked Word Count - nothing was actually
                        # measurable, so there's no honest percentage to
                        # report at all.
                        return {
                            "total_pages_analyzed": 0,
                            "thin_content_page_count": None,
                            "thin_content_percentage": None,
                            "page_details": [],
                            "note": note,
                        }
                    # Bug fix: this used to slice the first 20 rows in CSV
                    # order (results[:20]) before filtering, so on a large
                    # site the thin-content table could end up showing only
                    # a couple of thin pages that happened to appear early
                    # in the CSV, while the "N thin content URLs" stat above
                    # it (correctly computed over every row) reported a much
                    # bigger number - a real mismatch between the two.
                    # Filter to thin pages first, *then* cap - the frontend
                    # table only ever displays is_thin rows anyway, and 300
                    # is far more than any real site's thin-page count while
                    # still bounding the response for pathological inputs.
                    thin_pages = [r for r in results if r["is_thin"]]
                    return {
                        "total_pages_analyzed": len(results),
                        "thin_content_page_count": thin_count,
                        "thin_content_percentage": round((thin_count / len(results)) * 100, 2),
                        "page_details": thin_pages[:300],
                        "note": note,
                    }
            except Exception:
                pass

        # Option B: Fallback live page crawl if no valid CSV uploaded. A
        # failed fetch here used to report a specific fabricated word count
        # (1200 characters, 200 words) and unconditionally flag the page as
        # thin - a real number that looks measured but isn't. This reports
        # honestly instead: no page could be assessed at all.
        try:
            req = urllib.request.Request(target_url, headers={'User-Agent': 'Mozilla/5.0'})
            html = urllib.request.urlopen(req, timeout=5).read().decode('utf-8', errors='ignore')
            soup = BeautifulSoup(html, 'html.parser')
            for tag in soup(['nav', 'footer', 'header', 'script', 'style']):
                tag.extract()
            clean_text = re.sub(r'\s+', ' ', soup.get_text()).strip()
            c_count = len(clean_text)
            w_count = len(clean_text.split())
            is_thin = w_count < word_threshold
        except Exception as e:
            return {
                "total_pages_analyzed": 0,
                "thin_content_page_count": None,
                "thin_content_percentage": None,
                "page_details": [],
                "note": f"Couldn't fetch {target_url} to measure its content length: {e}",
            }

        if is_thin:
            thin_count += 1

        results.append({
            "url": target_url,
            "character_count": c_count,
            "word_count": w_count,
            "is_thin": is_thin
        })

        return {
            "total_pages_analyzed": len(results),
            "thin_content_page_count": thin_count,
            "thin_content_percentage": round((thin_count / len(results)) * 100, 2),
            "page_details": results,
            "note": None,
        }
