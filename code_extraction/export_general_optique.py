import requests
import pandas as pd
import re
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# =====================================================
# CONFIG
# =====================================================

URL = "https://api.generale-optique.com/graphql"

HASH = "eac4930742184d8482e250cd78e1ac4fba66f98eb0954a12d70cbeeb6f1f8b94"

OUTPUT = "generale_optique_stores.csv"

HEADERS = {
    "accept": "*/*",
    "accept-language": "fr-FR",
    "apollographql-client-name": "www-fr-generaleoptique",
    "apollographql-client-version": "www-fr-generaleoptique@v2026.31.0/runtime@browser",
    "content-type": "application/json",
    "origin": "https://www.generale-optique.com",
    "referer": "https://www.generale-optique.com/",
    "user-agent": "Mozilla/5.0"
}

MAX_WORKERS = 12
SAVE_EVERY = 50

_thread_local = threading.local()


def get_session():
    if not hasattr(_thread_local, "session"):
        _thread_local.session = requests.Session()
        _thread_local.session.headers.update(HEADERS)
    return _thread_local.session


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
    session = get_session()

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
        r = session.get(URL, params=params, timeout=20)
        if r.status_code != 200:
            return []
        data = r.json()
        return (
            data
            .get("data", {})
            .get("filteredResults", {})
            .get("results", [])
        )
    except Exception:
        return []


# =====================================================
# TRAITEMENT D'UNE ZONE
# =====================================================

def process_zone(lat, lon):
    results = fetch_stores(lat, lon)
    zone_stores = {}

    for s in results:
        sid = s.get("globalStoreId")
        if not sid:
            continue

        cp = s.get("postalCode")

        zone_stores[sid] = {
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

    return zone_stores


# =====================================================
# GRILLE GEO
# =====================================================

coords = []

for lat in range(420, 510, 2):
    for lon in range(-50, 81, 2):
        coords.append((lat/10, lon/10))

coords += [
    (16.2650, -61.5510),
    (14.6415, -61.0242),
    (4.9224, -52.3135),
    (-21.1151, 55.5364),
    (-12.8275, 45.1662),
]

print("=" * 60)
print(f"SCAN {len(coords)} ZONES  |  {MAX_WORKERS} threads simultanees")
print("=" * 60)

# =====================================================
# SCRAPING PARALLELISE
# =====================================================

stores = {}
stores_lock = threading.Lock()
completed = 0


def save_csv():
    pd.DataFrame(stores.values()).to_csv(
        OUTPUT,
        index=False,
        encoding="utf-8-sig"
    )


with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

    futures = {
        executor.submit(process_zone, lat, lon): (lat, lon)
        for lat, lon in coords
    }

    for future in as_completed(futures):

        lat, lon = futures[future]

        try:
            zone_stores = future.result()
        except Exception as e:
            print(f"  Erreur sur ({lat},{lon}) : {e}")
            zone_stores = {}

        with stores_lock:
            stores.update(zone_stores)
            completed += 1

            if completed % 50 == 0 or completed == len(coords):
                print(
                    f"  [{completed}/{len(coords)}]"
                    f"  zones traitees  |  {len(stores)} magasins uniques"
                )

            if completed % SAVE_EVERY == 0:
                save_csv()
                print(f"  Sauvegarde intermediaire ({len(stores)} magasins)")


# =====================================================
# EXPORT FINAL
# =====================================================

df = pd.DataFrame(stores.values())

df.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

print("\n" + "=" * 60)
print("TERMINE")
print("=" * 60)
print(f"Magasins : {len(df)}")
print(f"CSV      : {OUTPUT}")