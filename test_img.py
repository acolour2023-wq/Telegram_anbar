import urllib.parse
import re
import requests

def get_product_image_url(product_name, brand, barcode):
    queries = []
    if product_name:
        queries.append(f"{product_name} {brand}".strip())
        queries.append(product_name)
    if barcode and barcode != "-":
        queries.append(barcode)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for q in queries:
        try:
            url = f"https://www.bing.com/images/async?q={urllib.parse.quote(q)}"
            r = requests.get(url, headers=headers, timeout=3)
            # Find murl
            murls = re.findall(r'murl&quot;:&quot;(https?://[^&]+\.(?:jpg|jpeg|png|webp))', r.text, re.IGNORECASE)
            if murls:
                return murls[0]
            # Fallback to thurls
            thurls = re.findall(r'src="(https?://tse[0-9]\.mm\.bing\.net/th\?id=[^"]+)"', r.text)
            if thurls:
                return thurls[0]
        except Exception as e:
            continue
    return None

test_cases = [
    ("Effective Antiperspirant Men AKTIVE FRESH 150 ml", "NUR GİDA", "8699444267708"),
    ("Walkin Active dalgali sunger hamar deriye ag", "LLC Sabrise", "4820184442566"),
    ("Morfose Sac Spreyi Ultra Strong 400ml", "Morfose", "8698655380046")
]

for name, brand, bc in test_cases:
    img = get_product_image_url(name, brand, bc)
    print(f"Product: '{name}' -> Image URL: {img}")
