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

# Chaque boutique est dans :
# div.col-xs-12.col-sm-6.col-md-4

cards = soup.select("div.col-xs-12.col-sm-6.col-md-4")

print(f"{len(cards)} boutiques trouvées")

for card in cards:

    a = card.find("a", href=True)

    if not a:
        continue

    # ==========================================
    # URL BOUTIQUE
    # ==========================================

    boutique_url = a["href"].strip()

    # ==========================================
    # IMAGE
    # ==========================================

    image = ""

    img = a.find("img")

    if img and img.get("src"):
        image = img["src"].strip()

    # ==========================================
    # NOM
    # ==========================================

    nom = ""

    title = a.select_one(".font-headings")

    if title:
        nom = title.get_text(" ", strip=True)

    # ==========================================
    # INFOS TEXTE
    # ==========================================

    infos = a.select(".xs-font-x110")

    adresse = ""
    telephone = ""

    if len(infos) >= 1:
        adresse = infos[0].get_text(" ", strip=True)

    if len(infos) >= 2:
        telephone = infos[1].get_text(" ", strip=True)

    # ==========================================
    # CODE POSTAL
    # ==========================================

    code_postal = ""

    cp_match = re.search(r"\b\d{5}\b", adresse)

    if cp_match:
        code_postal = cp_match.group(0)

    # ==========================================
    # VILLE
    # ==========================================

    ville = ""

    if code_postal:

        split_cp = adresse.split(code_postal)

        if len(split_cp) > 0:
            avant_cp = split_cp[0]

            # Exemple :
            # "16 rue Marceau - "
            # On prend après le dernier tiret
            if "-" in avant_cp:
                ville = avant_cp.split("-")[-1].strip()

    # ==========================================
    # AJOUT
    # ==========================================

    boutiques.append({
        "nom": nom,
        "adresse": adresse,
        "code_postal": code_postal,
        "ville": ville,
        "telephone": telephone,
        "url_boutique": boutique_url,
        "image": image
    })

# ==========================================
# EXPORT CSV
# ==========================================

df = pd.DataFrame(boutiques)

df = df.drop_duplicates()

output = "edgard_opticiens.csv"

df.to_csv(
    output,
    sep=";",
    encoding="utf-8-sig",
    index=False
)

print("\n===================================")
print("SCRAP TERMINE")
print(f"{len(df)} boutiques exportées")
print(f"Fichier : {output}")
print("===================================")