import requests
import pandas as pd
import time
import re
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# =====================================================
# CONFIG
# =====================================================

URL = "https://api.grandoptical.com/graphql"

HASH = "eac4930742184d8482e250cd78e1ac4fba66f98eb0954a12d70cbeeb6f1f8b94"

OUTPUT = "grandoptical_stores.csv"

HEADERS = {
    "accept": "*/*",
    "accept-language": "fr-FR",
    "content-type": "application/json",
    "origin": "https://www.grandoptical.com",
    "referer": "https://www.grandoptical.com/",
    "user-agent": "Mozilla/5.0"
}

MAX_WORKERS = 30
SLEEP_BETWEEN_CALLS = 0.05
SAVE_EVERY = 50


# =====================================================
# FORMAT TELEPHONE
# =====================================================

def format_phone(phone):
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if digits.startswith("33"):
        digits = "0" + digits[2:]
    if len(digits) == 10:
        return " ".join(digits[i:i+2] for i in range(0, 10, 2))
    return digits


# =====================================================
# DEPARTEMENT
# =====================================================

def extract_department(cp):
    if not cp:
        return ""
    cp = str(cp)
    for dom in ["971", "972", "973", "974", "976"]:
        if cp.startswith(dom):
            return dom
    if cp.startswith("20"):
        return "2A/2B"
    return cp[:2]


# =====================================================
# API CALL
# =====================================================

def fetch_stores(lat, lon):

    variables = {
        "input": {
            "maxResults": 30,
            "searchGeoLocation": {
                "lat": lat,
                "lon": lon
            },
            "appointmentTypeIds": [],
            "filters": [],
            "forceDistance": True
        }
    }

    extensions = {
        "persistedQuery": {
            "version": 1,
            "sha256Hash": HASH
        }
    }

    params = {
        "operationName": "StoresSearchWithoutInventory",
        "variables": json.dumps(variables, separators=(",", ":")),
        "extensions": json.dumps(extensions, separators=(",", ":"))
    }

    try:
        r = requests.get(URL, headers=HEADERS, params=params, timeout=20)
        if r.status_code != 200:
            return []
        data = r.json()
        return (
            data
            .get("data", {})
            .get("filteredResults", {})
            .get("results", [])
        )
    except:
        return []


# =====================================================
# GRILLE GEO (France + DOM)
# =====================================================

coords = []

GRID_STEP = 5

for lat in range(420, 510, GRID_STEP):
    for lon in range(-50, 81, GRID_STEP):
        coords.append((lat / 10, lon / 10))

coords += [
    (16.2650, -61.5510),
    (14.6415, -61.0242),
    (4.9224, -52.3135),
    (-21.1151, 55.5364),
    (-12.8275, 45.1662),
]

print("=" * 60)
print(f"SCAN {len(coords)} ZONES GRANDOPTICAL")
print("=" * 60)

# =====================================================
# SCRAP
# =====================================================

stores = {}
stores_lock = threading.Lock()


def process_zone(item):
    i, (lat, lon) = item

    results = fetch_stores(lat, lon)
    time.sleep(SLEEP_BETWEEN_CALLS)

    new_count = 0

    with stores_lock:
        for s in results:

            sid = s.get("globalStoreId")
            if not sid:
                continue

            if sid not in stores:
                new_count += 1

            cp = s.get("postalCode")

            stores[sid] = {
                "id":          sid,
                "code":        s.get("code"),
                "slug":        s.get("slug"),
                "nom":         s.get("name"),
                "adresse":     " ".join(filter(None, [
                                   str(s.get("streetNumber") or "").strip(),
                                   str(s.get("streetName") or "").strip(),
                                   str(s.get("additionalStreetInfo") or "").strip()
                               ])),
                "cp":          cp,
                "ville":       s.get("town"),
                "region":      s.get("province"),
                "pays":        s.get("country"),
                "departement": extract_department(cp),
                "latitude":    s.get("lat"),
                "longitude":   s.get("lon"),
                "telephone":   format_phone(s.get("phone")),
                "email":       s.get("email"),
            }

        total = len(stores)

    return i, lat, lon, len(results), new_count, total


processed = 0

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = [executor.submit(process_zone, item) for item in enumerate(coords, 1)]

    for future in as_completed(futures):
        i, lat, lon, found, new_count, total = future.result()
        processed += 1

        print(f"[{i}/{len(coords)}] {lat},{lon} -> {found} magasins ({new_count} nouveaux, {total} total)")

        if processed % SAVE_EVERY == 0:
            with stores_lock:
                pd.DataFrame(stores.values()).to_csv(
                    OUTPUT,
                    index=False,
                    encoding="utf-8-sig"
                )


# =====================================================
# FINAL EXPORT
# =====================================================

df = pd.DataFrame(stores.values())

df.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

print("\n" + "=" * 60)
print("TERMINE GRANDOPTICAL")
print("=" * 60)
print(f"Boutiques : {len(df)}")
print(f"Fichier : {OUTPUT}")