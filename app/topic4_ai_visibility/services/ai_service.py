class Topic4Service:
    def get_audit_data(self):
        return {
            "target_url": "https://example.com",
            "summary": {
                "engine_visibility": "3/4",
                "cited_urls_count": 14,
                "cited_search_terms_count": 8,
                "score_percent": 20
            },
            "main_visibility": {
                "engines": [
                    {"name": "Gemini", "cited": True},
                    {"name": "Claude", "cited": True},
                    {"name": "Sonar", "cited": False},
                    {"name": "GPT", "cited": True}
                ],
                "share": [
                    {"name": "GPT", "percent": 40},
                    {"name": "Gemini", "percent": 30},
                    {"name": "Claude", "percent": 20},
                    {"name": "Sonar", "percent": 10}
                ]
            },
            "competitor_breakdown": [
                {"name": "Brand A", "share": 45},
                {"name": "Brand B", "share": 30},
                {"name": "Target Domain", "share": 25}
            ],
            "top_visible_terms": ["best audit tool", "ai seo scanner", "wcag compliance software"],
            "top_visible_urls": ["https://example.com/audit", "https://example.com/pricing"]
        }
