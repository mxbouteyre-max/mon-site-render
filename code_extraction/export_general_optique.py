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

# Nombre de requêtes simultanées. 12 est un bon compromis vitesse/politesse
# envers l'API GraphQL. En dessous de 8 le gain est limité, au-dessus de 20
# on risque des erreurs de rate-limiting.
MAX_WORKERS = 12

# Sauvegarde CSV intermédiaire toutes les N requêtes traitées
SAVE_EVERY = 50

# Session HTTP par thread (réutilise les connexions TCP/TLS, évite de les
# rouvrir à chaque requête comme le ferait requests.get() brut)
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
# API CALL (exécuté par les threads)
# =====================================================

def fetch_stores(lat, lon):
    """Interroge l'API GraphQL pour une coordonnée et retourne la liste
    des magasins trouvés. Retourne [] silencieusement en cas d'erreur
    (réseau, timeout, réponse malformée)."""

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
# TRAITEMENT D'UNE ZONE (appelé par chaque thread)
# =====================================================

def process_zone(lat, lon):
    """Récupère et normalise les magasins pour une coordonnée.
    Retourne un dict {globalStoreId: store_data}."""

    results = fetch_stores(lat, lon)
    zone_stores = {}

    for s in results:

        sid = s.get("globalStoreId")

        if not sid:
            continue

        zone_stores[sid] = {

            # ID
            "code": s.get("code"),
            "globalStoreId": sid,
            "slug": s.get("slug"),

            # NOMS
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

            "departement": extract_department(s.get("postalCode")),

            # GEO
            "lat": s.get("lat"),
            "lon": s.get("lon"),

            # CONTACT
            "email": s.get("email"),
            "phone_raw": s.get("phone"),
            "phone": format_phone(s.get("phone")),
        }

    return zone_stores


# =====================================================
# GRILLE GEO
# =====================================================

coords = []

# France métropolitaine (dense)
for lat in range(420, 510, 2):
    for lon in range(-50, 81, 2):
        coords.append((lat/10, lon/10))

# DOM
coords += [
    (16.2650, -61.5510),
    (14.6415, -61.0242),
    (4.9224, -52.3135),
    (-21.1151, 55.5364),
    (-12.8275, 45.1662),
]

print("=" * 60)
print(f"SCAN {len(coords)} ZONES  |  {MAX_WORKERS} threads simultanés")
print("=" * 60)

# =====================================================
# SCRAPING PARALLÉLISÉ
# =====================================================

stores = {}           # dict global dédupliqué par globalStoreId
stores_lock = threading.Lock()  # protège les écritures concurrentes
completed = 0         # compteur de zones traitées (protégé par stores_lock)


def save_csv():
    """Sauvegarde intermédiaire thread-safe (appelée sous stores_lock)."""
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
            print(f"  ⚠ Erreur sur ({lat},{lon}) : {e}")
            zone_stores = {}

        with stores_lock:
            stores.update(zone_stores)
            completed += 1

            # Affichage de progression
            if completed % 50 == 0 or completed == len(coords):
                print(
                    f"  [{completed}/{len(coords)}]"
                    f"  zones traitées  |  {len(stores)} magasins uniques"
                )

            # Sauvegarde intermédiaire toutes les SAVE_EVERY zones
            if completed % SAVE_EVERY == 0:
                save_csv()
                print(f"  💾 Sauvegarde intermédiaire ({len(stores)} magasins)")


# =====================================================
# EXPORT FINAL
# =====================================================

df = pd.DataFrame(stores.values())

df.to_csv(
    OUTPUT,
    index=False,
    encoding="utf-8-sig"
)

print("\n" + "=" * 60)
print("TERMINÉ")
print("=" * 60)
print(f"Magasins : {len(df)}")
print(f"CSV      : {OUTPUT}")
