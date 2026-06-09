import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import unquote
import re

BASE_URL = "https://www.auchan.fr"

LIST_URL = "https://www.auchan.fr/optique/ep-optique?"

headers = {
    "User-Agent": "Mozilla/5.0"
}

# ---------------------------------------------------
# Récupération des liens magasins
# ---------------------------------------------------

response = requests.get(LIST_URL, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")

magasins = []

for a in soup.select("li.lp-fiche a"):

    nom = a.get_text(strip=True)

    url = a.get("href")

    if url and url.startswith("/"):
        url = BASE_URL + url

    magasins.append({
        "nom": nom,
        "url": url
    })

print(f"{len(magasins)} magasins trouvés")

# ---------------------------------------------------
# Scraping des pages magasins
# ---------------------------------------------------

resultats = []

for magasin in magasins:

    print(f"Scraping : {magasin['nom']}")

    try:

        r = requests.get(magasin["url"], headers=headers)
        soup_mag = BeautifulSoup(r.text, "html.parser")

        # ---------------------------
        # Téléphone
        # ---------------------------

        telephone = ""

        tel_meta = soup_mag.find("meta", itemprop="telephone")

        if tel_meta:
            telephone = tel_meta.get("content", "").strip()

        # ---------------------------
        # Adresse via Google Maps
        # ---------------------------

        adresse = ""
        code_postal = ""
        ville = ""
        maps_link = ""

        for a in soup_mag.find_all("a", href=True):

            href = a["href"]

            if "maps.google.com/maps?q=" in href:

                maps_link = href

                # Décodage URL
                decoded = unquote(href)

                # On récupère ce qu'il y a après q=
                if "q=" in decoded:
                    adresse = decoded.split("q=")[1]

                break

        # ---------------------------
        # Extraction CP + ville
        # ---------------------------

        cp_match = re.search(r"\b(\d{5})\b", adresse)

        if cp_match:

            code_postal = cp_match.group(1)

            ville = adresse.split(code_postal)[-1].strip()

        # ---------------------------
        # Département
        # ---------------------------

        departement = ""

        if code_postal:

            if code_postal.startswith("20"):
                departement = "2A/2B"
            else:
                departement = code_postal[:2]

        # ---------------------------
        # Ajout résultat
        # ---------------------------

        resultats.append({
            "nom": magasin["nom"],
            "url": magasin["url"],
            "telephone": telephone,
            "adresse": adresse,
            "code_postal": code_postal,
            "ville": ville,
            "departement": departement,
            "google_maps": maps_link
        })

        time.sleep(1)

    except Exception as e:

        print(f"Erreur sur {magasin['nom']} : {e}")

# ---------------------------------------------------
# Création DataFrame
# ---------------------------------------------------

df = pd.DataFrame(resultats)

# ---------------------------------------------------
# Export CSV avec ;
# ---------------------------------------------------

df.to_csv(
    "auchan_optique.csv",
    index=False,
    encoding="utf-8-sig",
    sep=";"
)

print("CSV sauvegardé : auchan_optique.csv")