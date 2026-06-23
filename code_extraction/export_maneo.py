"""
Scraper magasins MANÉO
Stratégie :
  1. Récupère les 60 URLs depuis https://www.maneo.com/magasin-sitemap.xml
  2. Visite chaque page magasin et extrait nom, adresse, téléphone, email, maps
Sortie : maneo_magasins.csv (UTF-8 BOM, séparateur ;)

Utilisation :
    pip install requests beautifulsoup4 lxml
    python scraper_maneo.py
"""

import csv
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer": "https://www.maneo.com/",
}

SITEMAP_URL = "https://www.maneo.com/magasin-sitemap.xml"
OUTPUT_FILE = Path("maneo_magasins.csv")

FIELDNAMES = [
    "nom",
    "adresse",
    "complement_adresse",
    "cp",
    "ville",
    "telephone",
    "email",
    "url",
    "url_maps",
]


# ---------------------------------------------------------------------------
# Étape 1 — URLs depuis le sitemap
# ---------------------------------------------------------------------------

def get_store_urls() -> list[str]:
    resp = requests.get(SITEMAP_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    urls = re.findall(r"<loc>(https://www\.maneo\.com/magasin/[^<]+)</loc>", resp.text)
    # Dédoublonne en conservant l'ordre
    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


# ---------------------------------------------------------------------------
# Étape 2 — Parser chaque page magasin
# ---------------------------------------------------------------------------

def parse_store_page(url: str) -> dict:
    row = {f: "" for f in FIELDNAMES}
    row["url"] = url

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"    ✗ Erreur fetch : {e}")
        return row

    soup = BeautifulSoup(resp.text, "lxml")

    # --- Nom ---
    h1 = soup.find("h1")
    if h1:
        row["nom"] = h1.get_text(strip=True)
    else:
        title = soup.find("title")
        if title:
            row["nom"] = title.get_text(strip=True).split(" - ")[0].strip()

    # --- Téléphone : <div class="telephone"> ---
    tel_div = soup.find("div", class_="telephone")
    if tel_div:
        row["telephone"] = tel_div.get_text(strip=True)

    # --- Email : span contenant @ dans les listes d'icônes ---
    for span in soup.find_all("span", class_="dsm_icon_list_text"):
        text = span.get_text(strip=True)
        if "@" in text:
            row["email"] = text
            break
    # Fallback : cherche n'importe quel lien mailto
    if not row["email"]:
        mailto = soup.find("a", href=re.compile(r"^mailto:"))
        if mailto:
            row["email"] = mailto["href"].replace("mailto:", "").strip()

    # --- Adresse : div.adresse → <p> avec les <br> ---
    adresse_div = soup.find("div", class_=lambda c: c and "adresse" in c.split())
    if adresse_div:
        p = adresse_div.find("p")
        if p:
            lines = [t.strip() for t in p.stripped_strings]
            # Filtre liens Google Maps et lignes vides
            lines = [
                l for l in lines
                if l
                and "itinéraire" not in l.lower()
                and "google" not in l.lower()
            ]
            if lines:
                # Dernière ligne = "CP - Ville" ou "CP Ville"
                cp_ville = lines[-1]
                adresse_lines = lines[:-1]

                # Sépare adresse et complément
                if len(adresse_lines) >= 2:
                    row["adresse"] = adresse_lines[0]
                    row["complement_adresse"] = " ".join(adresse_lines[1:])
                elif len(adresse_lines) == 1:
                    row["adresse"] = adresse_lines[0]

                # Parse CP + Ville (formats: "46000 - CAHORS" ou "46000 CAHORS")
                m = re.match(r"(\d{5})\s*[-–]?\s*(.+)", cp_ville)
                if m:
                    row["cp"] = m.group(1)
                    row["ville"] = m.group(2).strip()
                else:
                    row["ville"] = cp_ville

    # --- URL Google Maps ---
    maps_a = soup.find("a", href=re.compile(r"google\.com/maps"))
    if maps_a:
        row["url_maps"] = maps_a["href"]

    return row


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== Scraper MANÉO ===\n")

    print(f"→ Récupération des URLs depuis {SITEMAP_URL}...")
    try:
        store_urls = get_store_urls()
    except Exception as e:
        print(f"  ✗ Impossible de lire le sitemap : {e}")
        return

    print(f"  ✓ {len(store_urls)} URLs trouvées\n")
    print("→ Scraping des pages magasins...\n")

    rows = []
    for i, url in enumerate(store_urls, 1):
        print(f"  [{i:>2}/{len(store_urls)}] {url.split('/')[-2]:<30}", end=" ")
        row = parse_store_page(url)
        print(f"→ {row['telephone'] or '?tel'} | {row['email'] or '?mail'}")
        rows.append(row)
        time.sleep(0.4)  # poli avec le serveur

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
            f"{r['cp']} {r['ville']:<18} | "
            f"{r['telephone']:<14} | {r['email']}"
        )


if __name__ == "__main__":
    main()