"""
Scraper - Le Collectif des Lunetiers
=====================================
Stratégie : quadrillage de la France métropolitaine avec des points espacés
de ~3.5° (~390km), rayon de 500km par requête, déduplique par store id.

Output : lunetiers_stores.csv
"""

import requests
import csv
import time
import json

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL  = "https://www.lecollectifdeslunetiers.fr"
STORE_URL = f"{BASE_URL}/ajax.V1.php/fr_FR/Rbs/Storelocator/Store/"
PAGE_URL  = f"{BASE_URL}/recherche-des-magasins"

WEBSITE_ID    = 2462577
SECTION_ID    = 2462577
PAGE_ID       = 2506921
LIMIT         = 50
RADIUS        = "500kilometers"
DISTANCE_UNIT = "kilometers"

# ---------------------------------------------------------------------------
# Grille de points couvrant la France métropolitaine
# ---------------------------------------------------------------------------

GRID_POINTS = [
    (lat, lon)
    for lat in [42.5, 45.5, 48.5, 51.0]
    for lon in [-4.5, -1.0, 2.5, 6.0, 8.5]
] + [
    # DOM-TOM
    (14.6,  -61.0),   # Martinique
    (16.2,  -61.5),   # Guadeloupe
    ( 4.9,  -52.3),   # Guyane
    (-20.9,   55.5),  # La Réunion
    (-12.8,   45.1),  # Mayotte
    (-21.1, -175.2),  # Wallis-et-Futuna
    (-17.7, -149.4),  # Polynésie française (Tahiti)
    (-22.3,  166.4),  # Nouvelle-Calédonie
    (47.0,   -56.3),  # Saint-Pierre-et-Miquelon
    (18.1,   -63.1),  # Saint-Martin / Saint-Barthélemy
]

# ---------------------------------------------------------------------------
# Session avec cookie automatique
# ---------------------------------------------------------------------------

def make_session() -> requests.Session:
    """Fait un GET sur la page principale pour obtenir un PHPSESSID valide."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
        "Accept-Language": "fr,fr-FR;q=0.9,en;q=0.8",
    })
    print("🔐 Récupération du cookie de session...")
    r = session.get(PAGE_URL, timeout=30)
    r.raise_for_status()
    phpsessid = session.cookies.get("PHPSESSID", "")
    print(f"   PHPSESSID={'OK' if phpsessid else 'ABSENT ⚠️'}")
    return session


def get_api_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr,fr-FR;q=0.9,en;q=0.8",
        "Origin": BASE_URL,
        "Referer": PAGE_URL,
        "x-http-method-override": "GET",  # ← valeur correcte
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
    }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_payload(lat: float, lon: float, offset: int) -> dict:
    return {
        "websiteId": WEBSITE_ID,
        "sectionId": SECTION_ID,
        "pageId": PAGE_ID,
        "referer": PAGE_URL,
        "URLFormats": "canonical,contextual",
        "data": {
            "currentStoreId": 0,
            "distanceUnit": DISTANCE_UNIT,
            "distance": RADIUS,
            "commercialSign": 0,
            "coordinates": {"latitude": lat, "longitude": lon},
        },
        "dataSets": "coordinates,address,card,allow,services,jsonLd",
        "pagination": f"{offset},{LIMIT}",
        "visualFormats": "original,listItem,200x200,300x300,400x400,500x500",
    }


def extract_store(item: dict) -> dict:
    # Les clés sont directement à la racine de l'item (pas dans dataSets)
    common = item.get("common", {})

    url = common.get("URL", {}).get("canonical", "")

    addr        = item.get("address", {})
    addr_fields = addr.get("fields", {})
    addr_lines  = addr.get("lines", [])

    coords = item.get("coordinates", {})

    card       = item.get("card", {})
    phone_data = card.get("phoneData", {})
    phone_nat  = phone_data.get("national", "")   # XX XX XX XX XX
    phone_e164 = phone_data.get("E164", card.get("phone", ""))
    email      = card.get("email", "")

    services_raw = item.get("services", [])
    services = " | ".join(
        s.get("common", {}).get("title", "")
        for s in services_raw
        if s.get("common", {}).get("title")
    )

    return {
        "id":               common.get("id", ""),
        "code":             common.get("code", ""),
        "nom":              common.get("title", ""),
        "url":              url,
        "latitude":         coords.get("latitude", ""),
        "longitude":        coords.get("longitude", ""),
        "adresse":          addr_fields.get("street", ""),
        "complement":       addr_fields.get("street_extend", ""),
        "code_postal":      addr_fields.get("zipCode", ""),
        "ville":            addr_fields.get("locality", ""),
        "pays":             addr_fields.get("countryCode", ""),
        "adresse_complete": " | ".join(l for l in addr_lines if l),
        "telephone":        phone_nat,
        "telephone_e164":   phone_e164,
        "email":            email,
        "services":         services,
    }


def fetch_page(session: requests.Session, lat: float, lon: float, offset: int) -> dict:
    r = session.post(
        STORE_URL,
        json=build_payload(lat, lon, offset),
        headers=get_api_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def scrape_all() -> list[dict]:
    session   = make_session()
    seen_ids  = set()
    stores    = []
    total_pts = len(GRID_POINTS)

    print(f"\n🗺  {total_pts} points de grille\n")

    for i, (lat, lon) in enumerate(GRID_POINTS, 1):
        print(f"[{i}/{total_pts}] ({lat:.1f}, {lon:.1f})", end="", flush=True)
        offset   = 0
        new_here = 0

        while True:
            try:
                data = fetch_page(session, lat, lon, offset)
            except requests.HTTPError as e:
                print(f"\n  ⚠️  HTTP {e}")
                break

            pagination = data.get("pagination", {})
            items      = data.get("items", [])
            count      = pagination.get("count", 0)

            for item in items:
                store = extract_store(item)
                sid   = store["id"]
                if sid and sid not in seen_ids:
                    seen_ids.add(sid)
                    stores.append(store)
                    new_here += 1

            offset += LIMIT
            if offset >= count or not items:
                break
            time.sleep(0.3)

        print(f"  → +{new_here} nouveaux (total: {len(stores)})")
        time.sleep(0.5)

    print(f"\n✅ {len(stores)} magasins uniques")
    return stores


def save_csv(stores: list[dict], path: str = "lunetiers_stores.csv") -> None:
    if not stores:
        print("Aucun magasin trouvé.")
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(stores[0].keys()))
        writer.writeheader()
        writer.writerows(stores)
    print(f"💾 {path}  ({len(stores)} lignes)")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    stores = scrape_all()
    save_csv(stores, "lunetiers_stores.csv")

    print("\n--- Aperçu du 1er magasin ---")
    if stores:
        print(json.dumps(stores[0], ensure_ascii=False, indent=2))