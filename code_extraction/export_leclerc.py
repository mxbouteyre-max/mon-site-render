import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time

BASE_URL = "https://optique.e-leclerc.com"
LIST_URL = f"{BASE_URL}/Shops"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

session = requests.Session()
session.headers.update(HEADERS)


def get_soup(url):

    response = session.get(url, timeout=30)
    response.raise_for_status()

    return BeautifulSoup(response.text, "html.parser")


# =====================================================
# RECUPERATION DES IDS BOUTIQUES
# =====================================================

print("Récupération des boutiques...")

soup = get_soup(LIST_URL)

shop_ids = set()

for inp in soup.select("input[onclick*='handleShopSelection']"):

    onclick = inp.get("onclick", "")

    match = re.search(r"handleShopSelection\('(\d+)'\)", onclick)

    if match:
        shop_ids.add(match.group(1))

shop_ids = sorted(shop_ids, key=int)

print(f"{len(shop_ids)} boutiques trouvées")


# =====================================================
# SCRAP DES FICHES
# =====================================================

data = []

for i, shop_id in enumerate(shop_ids, 1):

    url = f"{BASE_URL}/Shops/ShopInfos/{shop_id}"

    print(f"[{i}/{len(shop_ids)}] {url}")

    try:

        soup = get_soup(url)

        # -------------------------------------------------
        # BLOC PRINCIPAL
        # -------------------------------------------------

        bloc = soup.select_one(".addressShop")

        # NOM
        h2 = bloc.select_one("h2") if bloc else None
        nom = h2.get_text(" ", strip=True) if h2 else ""

        # LI
        li_tags = bloc.select("ul.selectShopDetail li") if bloc else []

        adresse = ""
        cp = ""
        ville = ""
        telephone = ""

        # ADRESSE
        if len(li_tags) >= 1:
            adresse = li_tags[0].get_text(" ", strip=True)

        # CP + VILLE
        if len(li_tags) >= 2:

            cp_ville = li_tags[1].get_text(" ", strip=True)

            match = re.match(r"(\d{5})\s+(.*)", cp_ville)

            if match:
                cp = match.group(1)
                ville = match.group(2)
            else:
                ville = cp_ville

        # TELEPHONE
        if len(li_tags) >= 3:
            telephone = li_tags[2].get_text(" ", strip=True)

        # -------------------------------------------------
        # AJOUT
        # -------------------------------------------------

        data.append({
            "id": shop_id,
            "nom": nom,
            "adresse": adresse,
            "cp": cp,
            "ville": ville,
            "telephone": telephone,
            "url": url
        })

        time.sleep(0.3)

    except Exception as e:

        print(f"Erreur sur {url}")
        print(e)


# =====================================================
# EXPORT CSV
# =====================================================

df = pd.DataFrame(data)

output_file = "optique_leclerc.csv"

df.to_csv(
    output_file,
    sep=";",
    encoding="utf-8-sig",
    index=False
)

print(f"\nCSV créé : {output_file}")