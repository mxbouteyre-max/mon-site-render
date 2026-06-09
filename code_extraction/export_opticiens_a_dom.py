import requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin

BASE_URL = "https://www.lopticienquibouge.fr/trouvez-un-opticien-a-domicile.html"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

# -------------------------------------------------
# Fonction de décodage des emails Cloudflare
# -------------------------------------------------
def decode_cfemail(encoded_string):
    r = int(encoded_string[:2], 16)
    email = ''.join(
        chr(int(encoded_string[i:i+2], 16) ^ r)
        for i in range(2, len(encoded_string), 2)
    )
    return email


print("Téléchargement de la page...")

response = requests.get(BASE_URL, headers=headers)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

resultats = []

# Chaque carte contient une div.Photo
cards = soup.select("div > div > div.Photo")

print(f"{len(cards)} cartes trouvées.")

for photo_div in cards:

    try:
        # Bloc parent complet
        card = photo_div.parent.parent

        divs = card.find_all("div", recursive=False)

        if len(divs) < 5:
            continue

        # Département
        departement = divs[1].get_text(strip=True)

        # Zone + Nom
        infos = divs[2].find_all("p")

        zone = infos[0].get_text(strip=True) if len(infos) > 0 else ""
        nom = infos[1].get_text(strip=True) if len(infos) > 1 else ""

        # Téléphone
        tel_tag = divs[3].select_one(".Telephone")
        telephone = tel_tag.get_text(strip=True) if tel_tag else ""

        # Email Cloudflare
        email = ""

        mail_tag = divs[3].select_one(".Mail a.__cf_email__")

        if mail_tag and mail_tag.has_attr("data-cfemail"):
            encoded = mail_tag["data-cfemail"]

            try:
                email = decode_cfemail(encoded)
            except Exception:
                email = ""

        # URL fiche
        lien_tag = divs[4].find("a")

        fiche_url = ""

        if lien_tag:
            fiche_url = urljoin(BASE_URL, lien_tag.get("href"))

        resultats.append({
            "departement": departement,
            "zone": zone,
            "nom": nom,
            "telephone": telephone,
            "email": email,
            "url_fiche": fiche_url
        })

    except Exception as e:
        print("Erreur :", e)

# -------------------------------------------------
# Export CSV
# -------------------------------------------------
df = pd.DataFrame(resultats)

output_file = "opticiens_domicile.csv"

df.to_csv(
    output_file,
    sep=";",
    index=False,
    encoding="utf-8-sig"
)

print(f"\nCSV sauvegardé : {output_file}")
print(df.head())