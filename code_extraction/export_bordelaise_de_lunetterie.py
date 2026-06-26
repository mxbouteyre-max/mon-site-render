import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
from urllib.parse import urljoin

BASE_URL = "https://www.bordelaisedelunetterie.com"
LIST_URL = f"{BASE_URL}/boutiques/"

headers = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# Récupération de la page principale
# =========================
response = requests.get(LIST_URL, headers=headers)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

boutiques = soup.find_all("article", class_=re.compile("post_card"))

print(f"{len(boutiques)} boutiques trouvées")

data = []

# =========================
# Boucle sur chaque boutique
# =========================
for boutique in boutiques:

    try:
        # Nom
        nom_tag = boutique.find("h3")
        nom = nom_tag.get_text(strip=True) if nom_tag else ""

        # Adresse
        adresse_tag = boutique.find("p", class_=re.compile("adresse"))
        adresse = adresse_tag.get_text(" ", strip=True) if adresse_tag else ""

        # Téléphone
        tel_tag = boutique.find("p", class_=re.compile("telephone"))
        telephone = tel_tag.get_text(" ", strip=True) if tel_tag else ""
        telephone = re.sub(r"\s+", " ", telephone).strip()

        # URL boutique
        lien_tag = boutique.find("a", href=True)
        url_boutique = ""
        if lien_tag:
            url_boutique = urljoin(BASE_URL, lien_tag["href"])

        # =========================
        # Infos supplémentaires dans la page boutique
        # =========================
        email = ""
        latitude = ""
        longitude = ""

        if url_boutique:

            try:
                r2 = requests.get(url_boutique, headers=headers, timeout=15)
                soup2 = BeautifulSoup(r2.text, "html.parser")

                texte_page = soup2.get_text(" ", strip=True)

                # Email
                mail = re.search(
                    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                    texte_page
                )
                if mail:
                    email = mail.group(0)

                # Coordonnées GPS
                html = str(soup2)
                lat_match = re.search(r'"lat"\s*:\s*"?(.*?)"?[,}]', html)
                lon_match = re.search(r'"lng"\s*:\s*"?(.*?)"?[,}]', html)
                if lat_match:
                    latitude = lat_match.group(1)
                if lon_match:
                    longitude = lon_match.group(1)

            except Exception as e:
                print(f"Erreur page boutique {nom} : {e}")

        # =========================
        # Extraction ville / CP / département
        # =========================
        code_postal = ""
        ville = ""
        departement = ""

        cp_match = re.search(r"\b(\d{5})\b", adresse)
        if cp_match:
            code_postal = cp_match.group(1)
            departement = code_postal[:2]

        ville_match = re.search(r"\b\d{5}\s+(.+)", adresse)
        if ville_match:
            ville = ville_match.group(1).strip()

        # =========================
        # Ajout dans la liste
        # =========================
        data.append({
            "nom":        nom,
            "adresse":    adresse,
            "cp":         code_postal,
            "ville":      ville,
            "departement": departement,
            "telephone":  telephone,
            "email":      email,
            "url":        url_boutique,
            "latitude":   latitude,
            "longitude":  longitude
        })

        print(f"OK : {nom}")
        time.sleep(1)

    except Exception as e:
        print(f"Erreur : {e}")

# =========================
# Export CSV
# =========================
df = pd.DataFrame(data)

output = "bordelaise_lunetterie_boutiques.csv"

df.to_csv(output, sep=";", index=False, encoding="utf-8-sig")

print(f"\nCSV enregistré : {output}")
print(df.head())