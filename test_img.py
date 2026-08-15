import urllib.parse
import re
import requests

def clean_query(name, brand):
    # Remove parenthetical noise like (top 20), (yeni), etc.
    c_name = re.sub(r'\(.*?\)', '', name).strip()
    # Remove extra spaces
    c_name = ' '.join(c_name.split())
    if brand and brand != "-" and brand.lower() not in c_name.lower():
        return f"{c_name} {brand}"
    return c_name

def get_product_thumb(name, brand):
    q = clean_query(name, brand)
    try:
        url = f"https://www.bing.com/images/async?q={urllib.parse.quote(q)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=3)
        # Match Bing's verified OIP image thumbnails
        thumbs = re.findall(r'https?://tse[0-9]\.mm\.bing\.net/th/id/OIP\.[^"\'\s\\?&]+', r.text)
        if thumbs:
            return thumbs[0]
        # Alternative pattern: th?id=OIP
        thumbs2 = re.findall(r'https?://[a-z0-9]+\.bing\.net/th\?id=OIP\.[^"\'\s\\&]+', r.text)
        if thumbs2:
            return thumbs2[0]
    except Exception as e:
        print("Error:", e)
    return None

test_items = [
    ("Sampun C/L Krapiva 250 ml noviy (top 20)", "KALINA"),
    ("Morfose Sac Spreyi Ultra Strong 400ml", "Morfose"),
    ("Walkin Active dalgali sunger hamar deriye ag", "LLC Sabrise"),
    ("İMPO ASETON", "Slavkov")
]

for name, brand in test_items:
    q_str = clean_query(name, brand)
    thumb = get_product_thumb(name, brand)
    print(f"Name: '{name}' | Clean: '{q_str}'")
    print(f"  Thumb: {thumb}\n")
