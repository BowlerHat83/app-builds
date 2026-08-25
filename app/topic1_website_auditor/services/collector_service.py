import json
from pathlib import Path

class Topic1Collector:
    """Mock collector for Topic 1 data."""
    def collect(self, url: str = None, use_mock: bool = True) -> dict:
        mock_path = Path(__file__).parent.parent / "mock_data" / "topic1_mock.json"
        if mock_path.exists():
            with open(mock_path, "r") as f:
                return json.load(f)
        return {}
