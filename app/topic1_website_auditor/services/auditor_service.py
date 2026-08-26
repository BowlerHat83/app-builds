class Topic1Service:
    def get_audit_data(self):
        return {
            "target_url": "https://example.com",
            "summary": {
                "sitemap_exists": True,
                "wcag_compliant": True,
                "gdpr_compliant": False,
                "score_percent": 88
            },
            "kpis": {
                "sitemap": "Passed",
                "ssl": "Valid",
                "html_syntax": "Clean",
                "wcag_compliance": "AA Compliant",
                "gdpr_compliance": "Action Needed"
            },
            "wcag": {
                "distribution": {
                    "critical": 1,
                    "serious": 2,
                    "moderate": 4,
                    "minor": 3,
                    "no_issues": 85
                },
                "issues": [
                    {"issue": "Low contrast on CTA button", "resolution": "Increase contrast ratio to 4.5:1"},
                    {"issue": "Missing alt text on logo", "resolution": "Add descriptive alt text"}
                ]
            },
            "gdpr": {
                "compliant": False,
                "provider": "OneTrust",
                "banner_exists": True,
                "yes_option": True,
                "no_option": True,
                "granular_categories": True,
                "pre_consent_cookies": 12,
                "post_consent_cookies": 24
            }
        }
