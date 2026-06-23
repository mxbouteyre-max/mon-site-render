"""
Scraper magasins Lunettes Pour Tous
Sortie : lpt_magasins.csv (UTF-8 BOM, séparateur ;)

Utilisation :
    pip install requests
    python scraper_lpt.py
"""

import csv
import sys
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Endpoint API trouvé via DevTools (Network > Fetch/XHR)
# ---------------------------------------------------------------------------
CANDIDATE_URLS = [
    "https://api.lpt-network.com/v1/stores/public",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": "https://lunettespourtous.com/",
    "Origin": "https://lunettespourtous.com",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
}

OUTPUT_FILE = Path("lpt_magasins.csv")

FIELDNAMES = [
    "nom", "adresse", "cp", "ville", "pays",
    "latitude", "longitude", "telephone", "email",
    "siret", "siren", "region",
]

def fetch_shops(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    for key in ("shops", "stores", "data", "results", "items"):
        if key in data and isinstance(data[key], list):
            return data[key]
    raise ValueError(f"Format JSON inattendu — clés : {list(data.keys())}")


def parse_shop(shop):
    addr  = shop.get("address", {})
    loc   = shop.get("location", {})

    row = {
        "nom":         shop.get("name", ""),
        "adresse":     addr.get("street", ""),
        "code_postal": addr.get("zip", ""),
        "ville":       addr.get("city", ""),
        "pays":        addr.get("country", ""),
        "latitude":    loc.get("lat", ""),
        "longitude":   loc.get("lng", ""),
        "telephone":   shop.get("phone", shop.get("tel", shop.get("phone_number", ""))),
        "email_sav":   shop.get("savEmail", shop.get("email", "")),
        "siret":  shop.get("siret", ""),
        "siren":  shop.get("siren", ""),
        "region": shop.get("region", ""),
    }

    return row


def main():
    shops_raw = None

    for url in CANDIDATE_URLS:
        print(f"→ Essai : {url}")
        try:
            shops_raw = fetch_shops(url)
            print(f"  ✓ {len(shops_raw)} magasins récupérés")
            break
        except requests.HTTPError as e:
            print(f"  HTTP {e.response.status_code} — {e.response.text[:300]}")
        except requests.ConnectionError as e:
            print(f"  Connexion refusée : {e}")
        except ValueError as e:
            print(f"  Format inattendu : {e}")
        except Exception as e:
            print(f"  Erreur inattendue : {e}")
        time.sleep(0.5)

    if shops_raw is None:
        print(
            "\n✗ Impossible de contacter l'API.\n"
            "  Si l'API exige un token, récupérez-le depuis DevTools\n"
            "  (Headers > Authorization) et ajoutez-le dans HEADERS ci-dessus.\n"
        )
        sys.exit(1)

    rows = [parse_shop(s) for s in shops_raw]

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=FIELDNAMES, delimiter=";", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✓ {len(rows)} magasins exportés → {OUTPUT_FILE.resolve()}")
    print("\n--- Aperçu (5 premiers) ---")
    for r in rows[:5]:
        print(
            f"  {r['nom']:<35} | "
            f"{r['adresse']}, {r['code_postal']} {r['ville']:<12} | "
            f"SIRET: {r['siret']}"
        )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        CANDIDATE_URLS.insert(0, sys.argv[1])
    main()