"""
export_duroc.py

Récupère les boutiques Optic Duroc via l'endpoint AJAX WordPress
(WP Store Locator) — sans Selenium, compatible Render free tier.

Action : store_search (GET), rayon 500km, plusieurs points de recherche.
"""

import re
import time
import requests
import pandas as pd

OUTPUT = "optic_duroc_boutiques.csv"

AJAX_URL = "https://opticduroc.com/wp-admin/admin-ajax.php"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://opticduroc.com/boutiques",
}

# Points couvrant la France entière
SEARCH_POINTS = [
    ("Paris",      48.8566,  2.3522),
    ("Lyon",       45.7640,  4.8357),
    ("Marseille",  43.2965,  5.3698),
    ("Bordeaux",   44.8378, -0.5792),
    ("Lille",      50.6292,  3.0573),
    ("Strasbourg", 48.5734,  7.7521),
    ("Nantes",     47.2184, -1.5536),
    ("Toulouse",   43.6047,  1.4442),
]


# ---------------------------------------------------
# FORMAT TELEPHONE
# ---------------------------------------------------
def format_phone(phone):
    if not phone:
        return ""
    phone = re.sub(r"[^\d+]", "", str(phone))
    prefixes = ["+33", "+262", "+590", "+594", "+596", "+687", "+689"]
    for prefix in prefixes:
        if phone.startswith(prefix):
            phone = "0" + phone[len(prefix):]
            break
    digits = re.sub(r"\D", "", phone)
    if len(digits) % 2 == 0:
        return " ".join(digits[i:i+2] for i in range(0, len(digits), 2))
    return digits


# ---------------------------------------------------
# EXTRACTION DEPARTEMENT
# ---------------------------------------------------
def extract_department(cp):
    if not cp:
        return ""
    cp = str(cp).strip()
    if cp.startswith("20"):
        return "2A/2B"
    dom = ["971", "972", "973", "974", "975", "976"]
    if cp[:3] in dom:
        return cp[:3]
    return cp[:2]


# ---------------------------------------------------
# SCRAPING
# ---------------------------------------------------
session = requests.Session()
session.headers.update(HEADERS)

stores = {}

for city, lat, lng in SEARCH_POINTS:
    print(f"\nRecherche autour de {city}...")

    params = {
        "action":        "store_search",
        "lat":           lat,
        "lng":           lng,
        "max_results":   100,
        "search_radius": 500,
        "skip_cache":    1,
    }

    try:
        resp = session.get(AJAX_URL, params=params, timeout=30)
        print(f"  Status : {resp.status_code}")

        if resp.status_code != 200:
            print(f"  ⚠ Réponse : {resp.text[:300]}")
            continue

        items = resp.json()

    except Exception as e:
        print(f"  ⚠ Erreur : {e}")
        continue

    if not isinstance(items, list):
        print(f"  ⚠ Format inattendu : {str(items)[:200]}")
        continue

    print(f"  → {len(items)} boutiques reçues")

    for store in items:
        store_id = str(store.get("id", ""))
        if store_id in stores:
            continue

        zip_code = str(store.get("zip", "") or "").strip()

        # URL : certaines sont relatives, d'autres absolues
        url = store.get("url", "")
        if url and not url.startswith("http"):
            url = "https://opticduroc.com" + url

        stores[store_id] = {
            "store_id":    store_id,
            "nom":         store.get("store", ""),
            "adresse":     store.get("address", ""),
            "cp":          zip_code,
            "ville":       store.get("city", ""),
            "departement": extract_department(zip_code),
            "pays":        store.get("country", ""),
            "telephone":   format_phone(store.get("phone", "")),
            "email":       store.get("email", ""),
            "latitude":    store.get("lat", ""),
            "longitude":   store.get("lng", ""),
            "url":   url,
        }

    time.sleep(0.3)


# ---------------------------------------------------
# EXPORT CSV
# ---------------------------------------------------
df = pd.DataFrame(stores.values()) if stores else pd.DataFrame()

if not df.empty:
    df = df.drop_duplicates(subset=["store_id"])

print(f"\nTotal boutiques uniques : {len(df)}")
df.to_csv(OUTPUT, sep=";", index=False, encoding="utf-8-sig")
print(f"CSV exporté : {OUTPUT}")