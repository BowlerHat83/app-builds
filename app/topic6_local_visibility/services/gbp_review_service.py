import httpx
from collections import Counter
from typing import Dict, Any, List, Optional

class GBPReviewService:
    async def get_reviews(
        self,
        business_name: str,
        location: str,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extracts GBP total review counts, average star rating, and collates top reviews.

        SerpApi's google_maps_reviews engine requires a real data_id or place_id -
        it does NOT accept a free-text business name/location search, and the
        "place_id" SerpApi's google_local engine returns is actually a raw
        internal CID, not a value google_maps_reviews accepts (confirmed via a
        live diagnostic: passing it produced "Google hasn't returned any
        results for this query" even though the same business genuinely has
        157 reviews at a 4.9 rating per that same google_local response).

        The engine that actually returns correctly-formatted identifiers is
        google_maps (not google_local) - its place_results/local_results carry
        both a proper place_id (ChIJ... format) and a data_id (0x...:0x... hex
        format), and google_maps_reviews accepts the data_id directly. So this
        method does its own two-step resolve-then-fetch instead of depending on
        whatever the map-pack check happened to resolve.
        """
        if not api_key:
            return {
                "business_name": business_name,
                "location": location,
                "data_source": "unavailable",
                "note": "No SerpApi key configured - review count/rating/top reviews unavailable. Set SERPAPI_KEY to enable.",
                "gbp_metrics": None,
                "top_reviews": []
            }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Step 1: resolve a data_id via google_maps
                resolve_resp = await client.get(
                    "https://serpapi.com/search.json",
                    params={
                        "engine": "google_maps",
                        "q": f"{business_name} {location}",
                        "type": "search",
                        "api_key": api_key,
                    },
                )
                resolve_data = resolve_resp.json()

                data_id = None
                matched_title = None

                place_results = resolve_data.get("place_results")
                if place_results and business_name.lower() in (place_results.get("title") or "").lower():
                    data_id = place_results.get("data_id")
                    matched_title = place_results.get("title")

                if not data_id:
                    for item in resolve_data.get("local_results", []):
                        if business_name.lower() in (item.get("title") or "").lower():
                            data_id = item.get("data_id")
                            matched_title = item.get("title")
                            break

                if not data_id:
                    return {
                        "business_name": business_name,
                        "location": location,
                        "data_source": "unavailable",
                        "note": (
                            "Could not resolve a Google Maps data_id for this business via "
                            "SerpApi's google_maps engine - review data can't be fetched "
                            "for this business right now."
                        ),
                        "gbp_metrics": None,
                        "top_reviews": []
                    }

                # Step 2: fetch reviews using the resolved data_id
                reviews_resp = await client.get(
                    "https://serpapi.com/search.json",
                    params={
                        "engine": "google_maps_reviews",
                        "data_id": data_id,
                        "api_key": api_key,
                    },
                )
                data = reviews_resp.json()

                search_status = data.get("search_metadata", {}).get("status")
                if search_status == "Error":
                    return {
                        "business_name": business_name,
                        "location": location,
                        "data_source": "unavailable",
                        "data_id": data_id,
                        "note": f"SerpApi returned an error for this data_id: {data.get('error', 'unknown error')}",
                        "gbp_metrics": None,
                        "top_reviews": []
                    }

                place_info = data.get("place_info", {})
                if not place_info:
                    return {
                        "business_name": business_name,
                        "location": location,
                        "data_source": "unavailable",
                        "data_id": data_id,
                        "note": (
                            "SerpApi returned no place_info for this data_id - "
                            "the listing may not have reviews data available "
                            "via this endpoint. Not the same as a confirmed 0 reviews."
                        ),
                        "gbp_metrics": None,
                        "top_reviews": []
                    }

                reviews_data = data.get("reviews", [])
                top_reviews = []
                for rev in reviews_data[:5]:
                    top_reviews.append({
                        "author": rev.get("user", {}).get("name", "Anonymous"),
                        "rating": rev.get("rating"),
                        "date": rev.get("date"),
                        "snippet": rev.get("snippet", "")
                    })

                # A 1-5 star distribution across every review this response
                # actually returned - free from the same call, only the top
                # 5 were being surfaced before. SerpApi's google_maps_reviews
                # returns one page of reviews (not the business's entire
                # review history), so this is a distribution over the
                # reviews_sampled count below, not necessarily every review
                # the listing has ever received - see total_reviews for the
                # real all-time count from place_info.
                rating_counts = Counter(
                    int(round(rev["rating"])) for rev in reviews_data if isinstance(rev.get("rating"), (int, float))
                )
                rating_distribution = {str(star): rating_counts.get(star, 0) for star in range(1, 6)}

                return {
                    "business_name": matched_title or business_name,
                    "location": location,
                    "data_source": "live_serpapi",
                    "data_id": data_id,
                    "gbp_metrics": {
                        "total_reviews": place_info.get("reviews", 0),
                        "average_rating": place_info.get("rating", 0.0),
                        "rating_stars": "★" * int(round(place_info.get("rating", 0.0)))
                    },
                    "top_reviews": top_reviews,
                    "rating_distribution": rating_distribution,
                    "reviews_sampled": len(reviews_data),
                }
        except Exception as e:
            return {
                "business_name": business_name,
                "location": location,
                "data_source": "unavailable",
                "error": f"SerpApi review lookup failed: {e}",
                "gbp_metrics": None,
                "top_reviews": []
            }
