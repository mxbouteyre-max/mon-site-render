import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

BASE_URL = "https://www.optiquelafayette.com"
START_URL = f"{BASE_URL}/magasins/"

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
# RECUPERATION DE TOUTES LES URLS DES BOUTIQUES
# =====================================================

store_urls = set()

page = 1

while True:

    if page == 1:
        url = START_URL
    else:
        url = f"{BASE_URL}/magasins/page/{page}/"

    print(f"Lecture page {page} : {url}")

    soup = get_soup(url)

    stores = soup.select(".store-locator-item")

    # Plus de boutiques = fin
    if not stores:
        print("Fin pagination")
        break

    for store in stores:

        a = store.select_one('a[href*="/opticien/"]')

        if a:
            href = a.get("href")

            if href.startswith("/"):
                href = BASE_URL + href

            store_urls.add(href)

    page += 1

    time.sleep(0.5)

store_urls = sorted(store_urls)

print(f"\nTotal boutiques trouvées : {len(store_urls)}")


# =====================================================
# SCRAP DES FICHES BOUTIQUES
# =====================================================

data = []

for i, url in enumerate(store_urls, 1):

    print(f"[{i}/{len(store_urls)}] {url}")

    try:

        soup = get_soup(url)

        # ---------------------------
        # Nom
        # ---------------------------

        h1 = soup.select_one("h1")

        nom = h1.get_text(" ", strip=True) if h1 else ""

        # ---------------------------
        # Sous titre
        # ---------------------------

        subtitle = soup.select_one(".subtitle")

        sous_titre = subtitle.get_text(" ", strip=True) if subtitle else ""

        # ---------------------------
        # Adresse
        # ---------------------------

        address = soup.select_one(".address p")

        adresse = address.get_text(" ", strip=True) if address else ""

        # ---------------------------
        # Téléphone
        # ---------------------------

        phone = soup.select_one(".phone a")

        telephone = phone.get_text(" ", strip=True) if phone else ""

        # ---------------------------
        # Horaires
        # ---------------------------

        horaires = []

        for el in soup.select(".time-wrapper *"):

            txt = el.get_text(" ", strip=True)

            if txt:
                horaires.append(txt)

        horaires = " | ".join(dict.fromkeys(horaires))

        # ---------------------------
        # Réseaux sociaux
        # ---------------------------

        social_links = []

        for a in soup.select(".social-wrap a[href]"):

            href = a.get("href")

            if href:
                social_links.append(href)

        social_links = " | ".join(social_links)

        # ---------------------------
        # Données
        # ---------------------------

        data.append({
            "nom": nom,
            "sous_titre": sous_titre,
            "adresse": adresse,
            "telephone": telephone,
            "horaires": horaires,
            "reseaux_sociaux": social_links,
            "url": url
        })

        time.sleep(0.5)

    except Exception as e:

        print(f"Erreur sur {url}")
        print(e)


# =====================================================
# EXPORT CSV
# =====================================================

df = pd.DataFrame(data)

output_file = "optiques_lafayette.csv"

df.to_csv(
    output_file,
    sep=";",
    encoding="utf-8-sig",
    index=False
)

print(f"\nCSV créé : {output_file}")