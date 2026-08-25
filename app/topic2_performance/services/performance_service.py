class Topic2Service:
    def get_audit_data(self):
        return {
            "target_url": "https://example.com",
            "summary": {
                "cwv_status": "PASS",
                "indexation_errors": False,
                "metadata_errors": True,
                "score_percent": 70
            },
            "cwv": {
                "lcp": "2.1s",
                "inp": "120ms",
                "cls": "0.04"
            },
            "meta_counts": {
                "missing": 1,
                "duplicate": 2,
                "multiple": 0
            },
            "title_distribution": {"under": 2, "optimal": 15, "over": 1},
            "description_distribution": {"under": 3, "optimal": 12, "over": 2},
            "tech_metrics": {
                "page_size": "1.4 MB",
                "ttfb": "180ms",
                "load_time": "1.2s",
                "canonicals": "Valid",
                "indexation_errors_count": 0
            }
        }
