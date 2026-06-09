"""
Scraper boutiques Afflelou
===========================
Usage :
    pip install requests
    python afflelou_scraper.py
"""

import csv
import time
import requests

BASE_URL  = "https://www.afflelou.com/afflelou_storelocator/location/getlist/"
PAGE_SIZE = 100
OUTPUT    = "boutiques_afflelou.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer": "https://www.afflelou.com/opticien",
    "X-Requested-With": "XMLHttpRequest",
}


def get_departement(code_postal):
    cp = str(code_postal).strip().zfill(5)
    if cp.startswith("97"):
        return cp[:3]
    return cp[:2]


def fetch_page(page):
    params = {
        "page": page,
        "pageSize": PAGE_SIZE,
        "isAudio": "false",
        "centerLat": 48.85,
        "centerLng": 2.35,
    }
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def parse_items(data):
    stores = []
    items  = data.get("data", {}).get("items", {})
    for mur_code, s in items.items():
        if s.get("country", "FR") != "FR":
            continue
        cp = s.get("zip", "")
        for loc in s.get("locations", [{}]):
            if loc.get("is_audio"):
                continue
            attrs   = loc.get("attributes", {})
            enseigne = attrs.get("enseigne", {}).get("value", "")
            stores.append({
                "id":          loc.get("id", ""),
                "enseigne":    enseigne,
                "adresse":     s.get("address", ""),
                "ville":       s.get("city", ""),
                "code_postal": cp,
                "departement": get_departement(cp),
                "telephone":   s.get("phone", ""),
                "latitude":    s.get("lat", ""),
                "longitude":   s.get("lng", ""),
                "url":         loc.get("url", ""),
            })
    return stores


def scrape():
    stores = []
    seen   = set()
    page   = 1

    data        = fetch_page(1)
    total_pages = data.get("data", {}).get("totalPages", 1)
    total_count = data.get("data", {}).get("totalCount", 0)

    print(f"Total annoncé par l'API : {total_count} | Pages : {total_pages}\n")

    while True:
        if page > 1:
            data = fetch_page(page)

        new_stores = parse_items(data)
        if not new_stores:
            break

        for s in new_stores:
            sid = s["id"] or f"{s['latitude']}_{s['longitude']}"
            if sid and sid not in seen:
                seen.add(sid)
                stores.append(s)

        done = int(30 * page / total_pages)
        bar  = "█" * done + "░" * (30 - done)
        print(f"\r  [{bar}] page {page}/{total_pages} — {len(stores)} boutiques", end="", flush=True)

        if page >= total_pages:
            break
        page += 1
        time.sleep(0.3)

    print()
    return stores


def save_csv(stores):
    if not stores:
        print("Aucune boutique trouvée.")
        return
    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(stores[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(stores)
    print(f"✅ {len(stores)} boutiques sauvegardées dans '{OUTPUT}'")


if __name__ == "__main__":
    print("=" * 45)
    print("  Scraper Boutiques Afflelou")
    print("=" * 45 + "\n")
    stores = scrape()
    save_csv(stores)