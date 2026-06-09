import requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin
import time

BASE_URL = "https://eye-like.fr/opticiens/"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

# -----------------------------
# 1. Récupération des liens boutiques
# -----------------------------
print("Récupération de la page principale...")

response = requests.get(BASE_URL, headers=headers)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

boutiques = []

# Chaque boutique est dans un div loop-item
items = soup.select("div[data-elementor-type='loop-item']")

for item in items:
    a_tag = item.select_one("a.loop_opticiens")

    if not a_tag:
        continue

    lien = a_tag.get("href")

    # Nom boutique
    nom_tag = item.select_one(".loop_titre .elementor-heading-title")
    nom = nom_tag.get_text(strip=True) if nom_tag else ""

    # Ville
    ville_tag = item.select_one(".loop_ville .elementor-heading-title")
    ville = ville_tag.get_text(strip=True) if ville_tag else ""

    boutiques.append({
        "nom": nom,
        "ville": ville,
        "url": lien
    })

print(f"{len(boutiques)} boutiques trouvées.")

# -----------------------------
# 2. Scraping des pages boutiques
# -----------------------------
resultats = []

for i, boutique in enumerate(boutiques, start=1):

    print(f"[{i}/{len(boutiques)}] {boutique['nom']}")

    try:
        r = requests.get(boutique["url"], headers=headers, timeout=20)
        r.raise_for_status()

        s = BeautifulSoup(r.text, "html.parser")

        # Bloc contact
        contact_items = s.select(
            ".liste_contact ul.elementor-icon-list-items li.elementor-icon-list-item"
        )

        adresse = ""
        telephone = ""

        for li in contact_items:

            texte = li.get_text(" ", strip=True)

            href = ""
            a = li.find("a")
            if a:
                href = a.get("href", "")

            # Téléphone
            if "tel:" in href:
                telephone = texte

            # Adresse
            elif "maps" in href or "google" in href:
                adresse = texte

        resultats.append({
            "nom": boutique["nom"],
            "ville": boutique["ville"],
            "adresse": adresse,
            "telephone": telephone,
            "url": boutique["url"]
        })

        time.sleep(1)

    except Exception as e:
        print(f"Erreur sur {boutique['url']} : {e}")

# -----------------------------
# 3. Export CSV
# -----------------------------
df = pd.DataFrame(resultats)

output_file = "opticiens_eye_like.csv"

df.to_csv(
    output_file,
    sep=";",
    index=False,
    encoding="utf-8-sig"
)

print(f"\nCSV sauvegardé : {output_file}")
print(df.head())