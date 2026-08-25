import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any

async def detect_forms(urls: List[str]) -> Dict[str, Any]:
    total_forms = 0
    total_ctas = 0
    forms_list = []

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for url in urls:
            try:
                res = await client.get(url)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    forms = soup.find_all('form')
                    ctas = soup.find_all(['button', 'a'], class_=lambda c: c and ('btn' in c or 'cta' in c or 'button' in c))
                    
                    total_forms += len(forms)
                    total_ctas += len(ctas)

                    for idx, f in enumerate(forms):
                        inputs = f.find_all(['input', 'textarea', 'select'])
                        forms_list.append({
                            "form_id": f.get('id', f"form_{idx+1}"),
                            "action": f.get('action', ''),
                            "number_of_inputs": len(inputs),
                            "appears_on": url
                        })
            except Exception as e:
                print(f"Error crawling {url}: {e}")

    avg_ctas = round(total_ctas / len(urls), 1) if urls else 0.0

    return {
        "total_forms": total_forms,
        "avg_ctas_per_page": avg_ctas,
        "forms_list": forms_list
    }
