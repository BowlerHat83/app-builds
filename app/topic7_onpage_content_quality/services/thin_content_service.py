import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any

async def analyze_thin_content(urls: List[str], word_threshold: int = 300) -> Dict[str, Any]:
    thin_urls = []

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for url in urls:
            try:
                res = await client.get(url)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    # Strip scripts and styles
                    for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                        element.decompose()
                    
                    text = soup.get_text(separator=' ', strip=True)
                    word_count = len(text.split())

                    if word_count < word_threshold:
                        thin_urls.append({
                            "url": url,
                            "word_count": word_count
                        })
            except Exception as e:
                print(f"Error parsing word count for {url}: {e}")

    return {
        "total_thin_urls": len(thin_urls),
        "thin_urls_list": thin_urls
    }
