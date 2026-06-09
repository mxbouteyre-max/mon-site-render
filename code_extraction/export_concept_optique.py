import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

URL = "https://concept-optique.com/boutiques/"

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(URL, headers=headers)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

boutiques = []

# Toutes les cartes boutiques
cards = soup.select("div.tuile.boutique")

for card in cards:

    # Nom boutique
    nom = ""
    h4 = card.find("h4")
    if h4:
        nom = h4.get_text(strip=True)

    # Texte brut de la carte
    texte = card.get_text("\n", strip=True)

    lignes = [l.strip() for l in texte.split("\n") if l.strip()]

    adresse = ""
    cp = ""
    ville = ""
    telephone = ""

    # Recherche téléphone
    tel_match = re.search(r'0\d(?:[\s\.]\d{2}){4}', texte)
    if tel_match:
        telephone = tel_match.group(0)

    # Adresse = lignes entre le nom et le téléphone
    adresse_lignes = []

    for ligne in lignes:

        if ligne == nom:
            continue

        if "Infos boutique" in ligne:
            continue

        if "T." in ligne or re.search(r'0\d(?:[\s\.]\d{2}){4}', ligne):
            continue

        adresse_lignes.append(ligne)

    adresse = " ".join(adresse_lignes)

    # Extraction CP / ville
    cp_ville_match = re.search(r'(\d{5})\s+(.+)', adresse)

    if cp_ville_match:
        cp = cp_ville_match.group(1)
        ville = cp_ville_match.group(2).strip()

    # Lien Google Maps
    google_maps = ""

    maps_link = card.find("a", href=True)

    if maps_link:
        google_maps = maps_link["href"]

    # URL page boutique
    page_boutique = ""

    lien_boutique = card.find("a", href=True)

    if lien_boutique:
        href = lien_boutique["href"]

        if "google.com/maps" not in href:

            if href.startswith("http"):
                page_boutique = href
            else:
                page_boutique = "https://concept-optique.com/" + href.lstrip("/")

    boutiques.append({
        "nom": nom,
        "adresse": adresse,
        "code_postal": cp,
        "ville": ville,
        "telephone": telephone,
        "google_maps": google_maps,
        "page_boutique": page_boutique
    })

# DataFrame
df = pd.DataFrame(boutiques)

# Suppression doublons éventuels
df = df.drop_duplicates()

# Export CSV
df.to_csv(
    "concept_optique_boutiques.csv",
    sep=";",
    index=False,
    encoding="utf-8-sig"
)

print(df)
print("\nCSV créé : concept_optique_boutiques.csv")