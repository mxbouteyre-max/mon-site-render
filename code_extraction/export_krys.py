import requests
import pandas as pd
import time
import re

URL = "https://www.krys.com/ajax.V1.php/fr_FR/Rbs/Storelocator/Store/"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://www.krys.com",
    "Referer": "https://www.krys.com/recherche-magasin",
    "X-HTTP-Method-Override": "GET"
}

SEARCH_POINTS = [
    ("Paris", 48.8566, 2.3522),
    ("Lille", 50.6292, 3.0573),
    ("Strasbourg", 48.5734, 7.7521),
    ("Lyon", 45.7640, 4.8357),
    ("Marseille", 43.2965, 5.3698),
    ("Bordeaux", 44.8378, -0.5792),
    ("Toulouse", 43.6047, 1.4442),
    ("Nantes", 47.2184, -1.5536),
]


# ---------------------------------------------------
# FORMAT TELEPHONE
# ---------------------------------------------------
def format_phone(phone):

    if not phone:
        return None

    phone = re.sub(r"[^\d+]", "", str(phone))

    prefixes = [
        "+33",
        "+262",
        "+590",
        "+594",
        "+596",
        "+687",
        "+689"
    ]

    for prefix in prefixes:
        if phone.startswith(prefix):
            phone = "0" + phone[len(prefix):]
            break

    digits = re.sub(r"\D", "", phone)

    # format xx xx xx xx xx
    if len(digits) % 2 == 0:
        return " ".join(
            digits[i:i+2]
            for i in range(0, len(digits), 2)
        )

    return digits


# ---------------------------------------------------
# EXTRACTION DEPARTEMENT
# ---------------------------------------------------
def extract_department(zip_code):

    if not zip_code:
        return None

    zip_code = str(zip_code)

    # Corse
    if zip_code.startswith("20"):
        return "2A/2B"

    # DOM
    dom = ["971", "972", "973", "974", "975", "976"]

    if zip_code[:3] in dom:
        return zip_code[:3]

    return zip_code[:2]


# ---------------------------------------------------
# SCRAPING
# ---------------------------------------------------
stores = {}

session = requests.Session()

for city, lat, lon in SEARCH_POINTS:

    print(f"\nRecherche autour de {city}")

    offset = 0
    total_count = None

    # sécurité anti boucle infinie
    seen_pages = set()

    while True:

        payload = {
            "websiteId": 100196,
            "sectionId": 100196,
            "pageId": 101077,

            "pagination": f"{offset},50",

            "dataSets": (
                "coordinates,address,card,"
                "allow,services,hours,jsonLd"
            ),

            "URLFormats": "canonical,contextual",

            "visualFormats": (
                "original,listItem,200x200,300x300,"
                "400x400,500x500"
            ),

            "referer": "https://www.krys.com/recherche-magasin",

            "data": {
                "currentStoreId": 0,
                "distanceUnit": "kilometers",
                "distance": "500kilometers",

                "coordinates": {
                    "latitude": lat,
                    "longitude": lon
                }
            }
        }

        response = session.post(
            URL,
            json=payload,
            headers=HEADERS,
            timeout=30
        )

        if response.status_code != 200:
            print(f"ERREUR {response.status_code}")
            break

        data = response.json()

        # total de magasins annoncé
        if total_count is None:
            total_count = data.get(
                "pagination",
                {}
            ).get("count", 0)

            print(f"Total magasins annoncés : {total_count}")

        items = data.get("items", [])

        print(f"Offset {offset} -> {len(items)} magasins")

        if not items:
            break

        # sécurité anti boucle infinie
        page_signature = tuple(
            item["common"]["id"]
            for item in items
        )

        if page_signature in seen_pages:
            print("Page répétée détectée -> arrêt")
            break

        seen_pages.add(page_signature)

        for store in items:

            store_id = store["common"]["id"]

            address = store.get(
                "address",
                {}
            ).get("fields", {})

            card = store.get("card", {})

            coords = store.get(
                "coordinates",
                {}
            )

            zip_code = address.get("zipCode")

            stores[store_id] = {

                # IDs
                "id": store_id,
                "code": store["common"].get("code"),

                # nom
                "nom": store["common"].get("title"),

                # contact
                "email": card.get("email"),
                "telephone": format_phone(
                    card.get("phone")
                ),

                # adresse
                "adresse": address.get("street"),
                "code_postal": zip_code,
                "departement": extract_department(
                    zip_code
                ),
                "ville": address.get("locality"),
                "pays": address.get("countryCode"),

                # géoloc
                "latitude": coords.get("latitude"),
                "longitude": coords.get("longitude"),

                # url
                "url": store["common"]["URL"].get(
                    "canonical"
                )
            }

        offset += 50

        # stop pagination
        if offset >= total_count:
            break

        time.sleep(0.25)


# ---------------------------------------------------
# EXPORT CSV
# ---------------------------------------------------
df = pd.DataFrame(stores.values())

# sécurité finale anti doublons
df = df.drop_duplicates(subset=["id"])

print(f"\nTotal magasins uniques : {len(df)}")

df.to_csv(
    "krys_stores.csv",
    index=False,
    encoding="utf-8-sig"
)

print("\nCSV exporté : krys_stores.csv")