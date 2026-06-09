import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import urljoin

BASE_URL = "https://www.direct-optic.fr/"

headers = {
    "User-Agent": "Mozilla/5.0"
}

# ==========================================
# 1. CHARGEMENT PAGE PRINCIPALE
# ==========================================

print("Chargement page principale...")

response = requests.get(BASE_URL, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")

# ==========================================
# 2. RECUPERATION DES REGIONS
# ==========================================

print("Récupération des régions...")

regions = []

# Les régions sont dans :
# .city-block .cities-content ul li a

for a in soup.select(".city-block .cities-content ul li a"):

    href = a.get("href")

    if href:

        full_url = urljoin(BASE_URL, href)

        if full_url not in regions:
            regions.append(full_url)

print(f"{len(regions)} régions trouvées")

for r in regions:
    print("-", r)

# ==========================================
# 3. SCRAP DES BOUTIQUES
# ==========================================

all_data = []

for region_url in regions:

    print("\n==============================")
    print("REGION :", region_url)

    try:

        r = requests.get(region_url, headers=headers, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")

        # Nom de la région
        region = ""

        region_title = soup.select_one(".popular-heading")

        if region_title:
            region = region_title.get_text(" ", strip=True)

        # Boutiques
        stores = soup.select(".store-list-detail ul li")

        print(f"{len(stores)} boutiques trouvées")

        for store in stores:

            # ==================================
            # NOM
            # ==================================
            nom = ""

            h6 = store.find("h6")

            if h6:
                nom = h6.get_text(" ", strip=True)

            # ==================================
            # URL BOUTIQUE
            # ==================================
            boutique_url = ""

            a = store.find("a", href=True)

            if a:
                boutique_url = urljoin(BASE_URL, a["href"])

            # ==================================
            # ADRESSE
            # ==================================
            adresse = ""

            p = store.find("p")

            if p:
                adresse = p.get_text(" ", strip=True)

            # ==================================
            # TELEPHONE
            # ==================================
            telephone = ""

            tel = store.find("a", href=re.compile(r"^tel:"))

            if tel:
                telephone = tel["href"].replace("tel:", "").strip()

            # ==================================
            # EMAIL
            # ==================================
            email = ""

            mail = store.find("a", href=re.compile(r"^mailto:"))

            if mail:
                email = mail["href"].replace("mailto:", "").strip()

            # ==================================
            # IMAGE
            # ==================================
            image = ""

            img = store.find("img")

            if img and img.get("src"):
                image = urljoin(BASE_URL, img["src"])

            # ==================================
            # CODE POSTAL
            # ==================================
            code_postal = ""

            cp_match = re.search(r"\b\d{5}\b", adresse)

            if cp_match:
                code_postal = cp_match.group(0)

            # ==================================
            # VILLE
            # ==================================
            ville = ""

            if code_postal:

                split_cp = adresse.split(code_postal)

                if len(split_cp) > 1:
                    ville = split_cp[1].split(",")[0].strip()

            # ==================================
            # AJOUT
            # ==================================
            all_data.append({
                "nom": nom,
                "region": region,
                "adresse": adresse,
                "code_postal": code_postal,
                "ville": ville,
                "telephone": telephone,
                "email": email,
                "url_boutique": boutique_url,
                "image": image
            })

    except Exception as e:
        print("Erreur :", e)

    time.sleep(1)

# ==========================================
# 4. EXPORT CSV
# ==========================================

df = pd.DataFrame(all_data)

df = df.drop_duplicates()

output = "direct_optic_boutiques.csv"

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