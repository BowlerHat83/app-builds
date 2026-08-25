class Topic3Service:
    def get_audit_data(self):
        return {
            "target_url": "https://example.com",
            "summary": {
                "domain_rating": 45,
                "avg_keyword_pos": 12.4,
                "total_impressions": 145000,
                "total_clicks": 3200,
                "score_percent": 75
            },
            "competitor_breakdown": [
                {"name": "Competitor A", "share": 35},
                {"name": "Competitor B", "share": 25},
                {"name": "Competitor C", "share": 20},
                {"name": "Target Domain", "share": 20}
            ],
            "top_keywords": [
                {"keyword": "seo software", "impressions": 12000, "clicks": 850, "position": 3},
                {"keyword": "audit tool", "impressions": 8500, "clicks": 420, "position": 5}
            ],
            "content_gaps": [
                {"topic": "Enterprise Reporting", "search_vol": 4500, "opportunity": "High"},
                {"topic": "API Integration Docs", "search_vol": 2100, "opportunity": "Medium"}
            ],
            "traffic_trend": [1200, 1500, 1800, 2100, 2400, 3200]
        }
