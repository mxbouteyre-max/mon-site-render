import requests
import pandas as pd
import time
import re
import json

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

for lat in range(420, 510, 2):
    for lon in range(-50, 81, 2):
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

for i, (lat, lon) in enumerate(coords, 1):

    print(f"\n[{i}/{len(coords)}] {lat},{lon}")

    results = fetch_stores(lat, lon)

    print(f"→ {len(results)} magasins")

    for s in results:

        sid = s.get("globalStoreId")

        if not sid:
            continue

        geo = {
            "lat": s.get("lat"),
            "lon": s.get("lon")
        }

        stores[sid] = {

            # IDENTIFIANTS
            "code": s.get("code"),
            "globalStoreId": sid,
            "slug": s.get("slug"),

            # NOM
            "name": s.get("name"),
            "shortName": s.get("shortName"),

            # ADRESSE
            "streetNumber": s.get("streetNumber"),
            "streetName": s.get("streetName"),
            "additionalStreetInfo": s.get("additionalStreetInfo"),

            "adresse_complete": " ".join(filter(None, [
                str(s.get("streetNumber") or "").strip(),
                str(s.get("streetName") or "").strip(),
                str(s.get("additionalStreetInfo") or "").strip()
            ])),

            # LOCALISATION
            "postalCode": s.get("postalCode"),
            "town": s.get("town"),
            "province": s.get("province"),
            "country": s.get("country"),

            "departement": extract_department(
                s.get("postalCode")
            ),

            # GEO
            "lat": geo["lat"],
            "lon": geo["lon"],

            # CONTACT
            "email": s.get("email"),
            "phone_raw": s.get("phone"),
            "phone": format_phone(s.get("phone")),
        }

    print(f"📦 Total unique: {len(stores)}")

    # sauvegarde live
    pd.DataFrame(stores.values()).to_csv(
        OUTPUT,
        index=False,
        encoding="utf-8-sig"
    )

    time.sleep(0.15)


# =====================================================
# FINAL EXPORT
# =====================================================

df = pd.DataFrame(stores.values())

df.to_csv(
    OUTPUT,
    index=False,
    encoding="utf-8-sig"
)

print("\n" + "=" * 60)
print("TERMINÉ GRANDOPTICAL")
print("=" * 60)
print(f"Boutiques : {len(df)}")
print(f"Fichier : {OUTPUT}")