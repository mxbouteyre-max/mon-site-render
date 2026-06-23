import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://fr.acuitis.com"

LIST_URL = "https://fr.acuitis.com/blogs/plus-dinformations/store-locator-acuitis"

headers = {
    "User-Agent": "Mozilla/5.0"
}

# Nombre de boutiques visitées en parallèle. 12 est un bon compromis entre
# vitesse et politesse envers le serveur (au-delà, le gain marginal diminue
# et le risque de rate-limiting / erreurs augmente).
MAX_WORKERS = 1  # séquentiel — évite tout rate-limiting

# Une session HTTP par thread est créée via threading.local pour réutiliser
# les connexions TCP/TLS au sein d'un même thread, au lieu d'en ouvrir une
# nouvelle à chaque requests.get() comme dans la version originale.
import time
import threading
_thread_local = threading.local()


def get_session():
    if not hasattr(_thread_local, "session"):
        _thread_local.session = requests.Session()
        _thread_local.session.headers.update(headers)
    return _thread_local.session


# =========================================================
# Récupération des liens boutiques
# =========================================================

response = requests.get(LIST_URL, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")

boutiques = []
urls_vues = set()

for a in soup.select("a.city-link"):

    nom = a.get_text(strip=True)

    url = a.get("href")

    if url.startswith("/"):
        url = BASE_URL + url

    # Évite les doublons
    if url not in urls_vues:

        urls_vues.add(url)

        boutiques.append({
            "nom": nom,
            "url": url
        })

print(f"{len(boutiques)} boutiques uniques trouvées")

# =========================================================
# Fonction extraction CP / ville
# =========================================================

def extract_cp_ville(adresse):

    cp = ""
    ville = ""

    match = re.search(r"(\d{5})\s+(.+)", adresse)

    if match:
        cp = match.group(1)
        ville = match.group(2).strip()

    return cp, ville

# =========================================================
# Scraping d'une boutique (exécuté en parallèle par les threads)
# =========================================================

def scrape_boutique(boutique):

    session = get_session()

    r = session.get(boutique["url"], timeout=20)
    # Pause légère pour éviter de déclencher le rate-limiting d'Acuitis.
    # Avec 4 workers × 0.5s de pause, on reste sous ~8 req/s.
    time.sleep(1.5)  # pause humaine — 254 boutiques × 1.5s ≈ 6 min
    soup_b = BeautifulSoup(r.text, "html.parser")

    # -------------------------------------------------
    # Type de boutique
    # -------------------------------------------------

    type_boutique = ""

    h1 = soup_b.select_one("h1.gw-store-hero__subtitle")

    if h1:
        type_boutique = h1.get_text(strip=True)

    # -------------------------------------------------
    # Nom boutique
    # -------------------------------------------------

    nom_boutique = boutique["nom"]

    h2 = soup_b.select_one("h2.gw-store-hero__title")

    if h2:
        nom_boutique = h2.get_text(strip=True)

    # -------------------------------------------------
    # Adresse
    # -------------------------------------------------

    adresse_complete = ""

    adresse_block = soup_b.select_one(
        "div.metafield-rich_text_field"
    )

    if adresse_block:

        lignes = [
            p.get_text(" ", strip=True)
            for p in adresse_block.find_all("p")
        ]

        adresse_complete = " | ".join(lignes)

    # -------------------------------------------------
    # CP / Ville
    # -------------------------------------------------

    code_postal, ville = extract_cp_ville(adresse_complete)

    # -------------------------------------------------
    # Département
    # -------------------------------------------------

    departement = ""

    if code_postal:

        if code_postal.startswith("20"):
            departement = "2A/2B"
        else:
            departement = code_postal[:2]

    # -------------------------------------------------
    # Téléphone
    # -------------------------------------------------

    telephone = ""

    tel = soup_b.select_one("a.gw-store-hero__phone")

    if tel:
        telephone = tel.get_text(strip=True)

    # -------------------------------------------------
    # Email
    # -------------------------------------------------

    email = ""

    email_link = soup_b.find(
        "a",
        href=lambda x: x and x.startswith("mailto:")
    )

    if email_link:

        email = email_link["href"].replace("mailto:", "").strip()

    # -------------------------------------------------
    # Google Maps + coordonnées GPS
    # -------------------------------------------------

    google_maps = ""
    latitude = ""
    longitude = ""

    maps_link = soup_b.find(
        "a",
        href=lambda x: x and "google.com/maps/dir" in x
    )

    if maps_link:

        google_maps = maps_link["href"]

        gps_match = re.search(
            r"destination=([-0-9\.]+)%2C([-0-9\.]+)",
            google_maps
        )

        if gps_match:

            latitude = gps_match.group(1)
            longitude = gps_match.group(2)

  

    # -------------------------------------------------
    # Résultat
    # -------------------------------------------------

    return {

        "nom": nom_boutique,
        "type": type_boutique,
        "url": boutique["url"],

        "adresse_complete": adresse_complete,
        "cp": code_postal,
        "ville": ville,
        "departement": departement,

        "telephone": telephone,
        "email": email,

        "latitude": latitude,
        "longitude": longitude,

        "google_maps": google_maps,

    }


# =========================================================
# Scraping des boutiques (parallélisé)
# =========================================================
# Les résultats sont stockés dans un dict indexé par position d'origine
# pour reconstituer l'ordre exact de la liste `boutiques` à la fin, même
# si les threads terminent dans le désordre.

resultats_par_index = {}

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

    futures = {
        executor.submit(scrape_boutique, boutique): (i, boutique)
        for i, boutique in enumerate(boutiques)
    }

    for future in as_completed(futures):

        i, boutique = futures[future]

        try:
            resultats_par_index[i] = future.result()
            print("Scraping OK :", boutique["nom"])

        except Exception as e:
            print("Erreur :", boutique["nom"], e)

# Reconstitue l'ordre d'origine (positions manquantes = échecs, ignorées)
resultats = [resultats_par_index[i] for i in range(len(boutiques)) if i in resultats_par_index]

# =========================================================
# DataFrame
# =========================================================

df = pd.DataFrame(resultats)

# =========================================================
# Export CSV
# =========================================================

df.to_csv(
    "acuitis_boutiques.csv",
    sep=";",
    index=False,
    encoding="utf-8-sig"
)

print("CSV sauvegardé : acuitis_boutiques.csv")