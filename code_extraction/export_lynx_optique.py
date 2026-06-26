"""
Scraper magasins Lynx Optique & YOU DO
Source : https://www.lynx-optique.com/ajax.V1.php/fr_FR/Rbs/Storelocator/Store/
Sortie : lynx_magasins.csv (UTF-8 BOM, séparateur ;)

Utilisation :
    pip install requests
    python scraper_lynx.py

Note : le PHPSESSID expire après ~30 min d'inactivité.
Si erreur 400 ou 401, relancez la page du site et copiez un nouveau PHPSESSID.
"""

import csv
import sys
import time
from collections import Counter
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# ⚠️  METTEZ À JOUR CE COOKIE SI VOUS OBTENEZ UNE ERREUR 400/401
# DevTools → Headers → Request Headers → valeur de "cookie"
# ---------------------------------------------------------------------------
COOKIE = (
    "PHPSESSID=2naP9TVGz8xvI3TC4h3aYfNd8asPHKvl; "
    "rbsWebsiteTrackerConsentGdpr=%7B%22acceptedCookies%22%3A%7B%22technical%22%3Atrue%2C%22analytics%22%3Atrue%2C%22advertising%22%3Atrue%7D%2C%22previousIdentifier%22%3Anull%2C%22consentMode%22%3A%22all%22%2C%22consentSource%22%3A%22banner%22%2C%22identifier%22%3A%228347a90b19fb418ed0bdc7016231f1851e4756f2%22%7D"
)

API_URL = "https://www.lynx-optique.com/ajax.V1.php/fr_FR/Rbs/Storelocator/Store/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr,fr-FR;q=0.9,en;q=0.8",
    "Content-Type": "application/json",
    "Origin": "https://www.lynx-optique.com",
    "Referer": "https://www.lynx-optique.com/recherche-des-magasins",
    "sec-ch-ua": '"Chromium";v="148", "Microsoft Edge";v="148", "Not/A)Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "x-http-method-override": "GET",   # ← clé manquante qui causait le 400
    "Cookie": COOKIE,
}

PAGE_SIZE   = 50
OUTPUT_FILE = Path("lynx_magasins.csv")

BASE_PAYLOAD = {
    "websiteId": 100230,
    "sectionId": 100230,
    "pageId":    101633,
    "URLFormats": "canonical,contextual",
    "dataSets":   "coordinates,address,card,allow,services,hours,jsonLd",
    "visualFormats": "original,listItem,200x200,300x300,400x400,500x500,600x600,700x700,800x800,1000x1000,1200x1200,1400x1400",
    "referer": "https://www.lynx-optique.com/recherche-des-magasins",
    "data": {
        "currentStoreId": 0,
        "distanceUnit": "kilometers",
        "distance": "20000kilometers",
        "commercialSign": 0,
        "coordinates": {
            "latitude":  48.8575475,
            "longitude": 2.3513765,
        },
    },
}

ENSEIGNE_MAP = {
    "LYX": "Lynx Optique",
    "YDO": "YOU DO",
    "YOU": "YOU DO",
}

FIELDNAMES = [
    "enseigne", "nom", "adresse", "complement_adresse",
    "cp", "ville", "pays",
    "latitude", "longitude",
    "telephone", "email",
    "url",
]


def build_payload(offset: int) -> dict:
    p = {**BASE_PAYLOAD, "pagination": f"{offset},{PAGE_SIZE}"}
    return p


def fetch_page(offset: int) -> list[dict]:
    resp = requests.post(API_URL, json=build_payload(offset), headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    for key in ("items", "stores", "data", "results", "storeList"):
        if key in data and isinstance(data[key], list):
            return data[key]
    if data and all(str(k).isdigit() for k in data.keys()):
        return list(data.values())
    raise ValueError(f"Format JSON inattendu — clés : {list(data.keys())[:10]}")


def get_enseigne(shop: dict) -> str:
    sign = shop.get("common", {}).get("commercialSign", "")
    return ENSEIGNE_MAP.get(sign, sign or "Lynx Optique")


def parse_store(shop: dict) -> dict:
    addr    = shop.get("address", {}).get("fields", {})
    card    = shop.get("card", {})
    common  = shop.get("common", {})
    coords  = shop.get("coordinates", {})
    appt    = shop.get("appointment", {})
    phone_d = card.get("phoneData", {})
    url     = common.get("URL", {})
    return {
        "enseigne":           get_enseigne(shop),
        "nom":                common.get("newTitle", common.get("title", addr.get("name", ""))),
        "adresse":            addr.get("street", ""),
        "complement_adresse": addr.get("street_extend", ""),
        "cp":        addr.get("zipCode", ""),
        "ville":              addr.get("locality", ""),
        "pays":               addr.get("countryCode", "FR"),
        "latitude":           coords.get("latitude", ""),
        "longitude":          coords.get("longitude", ""),
        "telephone":          phone_d.get("national", card.get("phone", "")),
        "email":              card.get("email", ""),
        "url":          url.get("canonical", ""),
    }


def main():
    all_rows = []
    offset   = 0
    print(f"→ API : {API_URL}")
    print(f"  POST + x-http-method-override: GET | page_size={PAGE_SIZE}\n")

    while True:
        print(f"  Offset {offset:>4} ... ", end="", flush=True)
        try:
            page = fetch_page(offset)
        except requests.HTTPError as e:
            print(f"\n✗ HTTP {e.response.status_code} : {e.response.text[:300]}")
            if e.response.status_code == 400:
                print(
                    "\n  → Le PHPSESSID a peut-être expiré.\n"
                    "  Rechargez la page du site, copiez le nouveau cookie\n"
                    "  et mettez à jour la variable COOKIE en haut du script.\n"
                )
            sys.exit(1)
        except Exception as e:
            print(f"\n✗ {e}")
            sys.exit(1)

        print(f"{len(page)} magasins")
        if not page:
            break
        all_rows.extend(parse_store(s) for s in page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(0.4)

    print(f"\n✓ Total : {len(all_rows)} magasins")
    for enseigne, n in sorted(Counter(r["enseigne"] for r in all_rows).items()):
        print(f"   {enseigne} : {n}")

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n✓ Exporté → {OUTPUT_FILE.resolve()}")
    print("\n--- Aperçu (5 premiers) ---")
    for r in all_rows[:5]:
        print(f"  [{r['enseigne']:<12}] {r['nom']:<40} | {r['cp']} {r['ville']:<15} | {r['telephone']}")


if __name__ == "__main__":
    main()