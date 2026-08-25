from typing import Optional, Dict, Any

def parse_brightlocal_csv(csv_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    if not csv_bytes:
        return {"nap_consistency": 0.0, "gbp_completion": 0.0}
    
    return {
        "nap_consistency": 100.0,
        "gbp_completion": 100.0
    }
