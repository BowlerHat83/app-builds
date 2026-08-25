from app.topic5_paid_visibility.mock_data import MOCK_PPC_KEYWORDS_DATABASE

class KeywordService:
    @staticmethod
    def get_targeted_keywords_count(domain: str) -> dict:
        domain_clean = domain.lower().strip()
        keywords = MOCK_PPC_KEYWORDS_DATABASE.get(domain_clean, [])
        count = len(keywords)
        return {"domain": domain_clean, "targeted_keywords_count": count, "has_active_ppc": count > 0}
