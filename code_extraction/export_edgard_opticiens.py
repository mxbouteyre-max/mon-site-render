import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

url = "https://www.edgard-opticiens.com/boutiques/"

headers = {
    "User-Agent": "Mozilla/5.0"
}

print("Chargement de la page...")

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")

# ==========================================
# RECUPERATION DES BOUTIQUES
# ==========================================

boutiques = []

cards = soup.select("div.col-xs-12.col-sm-6.col-md-4")

print(f"{len(cards)} boutiques trouvées")

for card in cards:

    a = card.find("a", href=True)

    if not a:
        continue

    # URL
    url_boutique = a["href"].strip()

    # Nom
    nom = ""
    title = a.select_one(".font-headings")
    if title:
        nom = title.get_text(" ", strip=True)

    # Adresse + téléphone
    infos = a.select(".xs-font-x110")
    adresse = ""
    telephone = ""

    if len(infos) >= 1:
        adresse = infos[0].get_text(" ", strip=True)
    if len(infos) >= 2:
        telephone = infos[1].get_text(" ", strip=True)

    # CP
    cp = ""
    cp_match = re.search(r"\b\d{5}\b", adresse)
    if cp_match:
        cp = cp_match.group(0)

    # Département
    departement = ""
    if cp:
        departement = cp[:2]

    # Ville
    ville = ""
    if cp:
        split_cp = adresse.split(cp)
        if len(split_cp) > 0:
            avant_cp = split_cp[0]
            if "-" in avant_cp:
                ville = avant_cp.split("-")[-1].strip()

    boutiques.append({
        "nom":         nom,
        "adresse":     adresse,
        "cp":          cp,
        "ville":       ville,
        "departement": departement,
        "telephone":   telephone,
        "url":         url_boutique,
    })

# ==========================================
# EXPORT CSV
# ==========================================

df = pd.DataFrame(boutiques)
df = df.drop_duplicates()

output = "edgard_opticiens.csv"

df.to_csv(output, sep=";", encoding="utf-8-sig", index=False)

print("\n===================================")
print("SCRAP TERMINE")
print(f"{len(df)} boutiques exportées")
print(f"Fichier : {output}")
print("===================================")