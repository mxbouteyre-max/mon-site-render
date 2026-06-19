"""
export_atol.py — Extraction des magasins Atol Optique/Audition

Découverte clé : le store locator (https://magasins.atol.fr/) expose une
route /resultats qui, appelée avec __xhr=1, renvoie un fragment JSON
contenant jusqu'à 10 fiches magasin en HTML (clé results.items) ainsi que
le nombre total de résultats (results.total) et de pages (results.last_page).

Cette recherche, bien que basée sur un point central (p) et une bounding
box d'affichage (b), retourne en réalité l'intégralité du réseau Atol
(métropole + DOM-TOM, ~910 fiches), simplement triées par distance
croissante au point de recherche. Il suffit donc de paginer cette unique
requête (page=1 à last_page) pour tout récupérer, sans quadrillage
géographique.

Le numéro de téléphone est protégé côté client par une simple table de
substitution fixe (chaque caractère de "DD DD DD DD DD" est remplacé par
une valeur hexadécimale qui lui est propre, indépendamment du magasin).
Cette table a été reconstituée par recoupement avec plusieurs numéros
publics connus (voir PHONE_DECODE_TABLE ci-dessous) et validée sans aucun
conflit sur 4 magasins différents.
"""

import csv
import re
import time

import requests
from bs4 import BeautifulSoup

BASE_RESULTS_URL = "https://magasins.atol.fr/resultats"
OUTPUT_FILE = "magasins.csv"

# Point de recherche central et bounding box d'affichage : peu importe leurs
# valeurs exactes, la pagination de cette route couvre tout le réseau.
SEARCH_PARAMS = {
    "q": "Paris, France",
    "p": "48.8566,2.3522",
    "s": "geocoder",
    "b": "48.81,2.25,48.90,2.45",
    "__xhr": "1",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

REQUEST_DELAY = 0.3  # pause entre deux pages, pour rester courtois envers le serveur

# ── table de décodage du téléphone protégé (data-protected-text) ───────────
# Reconstituée par recoupement de 4 numéros publics connus (Monge, Lecourbe,
# Access Paris 12e, Malakoff). Format attendu : "DD DD DD DD DD" (10 chiffres
# + 4 espaces = 14 caractères), chaque caractère étant remplacé par sa
# valeur dans cette table.
PHONE_DECODE_TABLE = {
    32: "0", 42: "1", 33: "2", 34: "3", 43: "4",
    35: "5", 36: "6", 44: "7", 37: "8", 38: "9",
    16: " ",
}


def decode_phone(protected_text):
    """Décode un numéro de téléphone à partir de son attribut
    data-protected-text (chaîne hexadécimale). Retourne '' si le format
    est inattendu ou si un caractère ne correspond à aucune entrée connue
    de la table (mieux vaut un champ vide qu'un numéro erroné)."""
    if not protected_text:
        return ""
    try:
        byte_values = [
            int(protected_text[i:i + 2], 16)
            for i in range(0, len(protected_text), 2)
        ]
    except ValueError:
        return ""

    decoded_chars = []
    for v in byte_values:
        if v not in PHONE_DECODE_TABLE:
            return ""  # caractère inconnu -> on n'invente rien, on abandonne
        decoded_chars.append(PHONE_DECODE_TABLE[v])

    decoded = "".join(decoded_chars).strip()
    digits = re.sub(r"\D", "", decoded)
    if len(digits) != 10:
        return ""
    return decoded


# ── récupération d'une page de résultats ────────────────────────────────────
def fetch_results_page(session, page):
    params = dict(SEARCH_PARAMS)
    if page > 1:
        params["page"] = page
    resp = session.get(BASE_RESULTS_URL, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def parse_store_fragment(article_html):
    """Parse un fragment <article class="b-result">...</article> et en
    extrait les données du magasin."""
    soup = BeautifulSoup(article_html, "html.parser")
    article = soup.find("article")
    data = {
        "nom": "", "adresse": "", "cp": "", "ville": "",
        "telephone": "", "note": "", "nb_avis": "",
        "url": "", "latitude": "", "longitude": "",
    }
    if article is None:
        return data

    if article.has_attr("data-lat"):
        data["latitude"] = article["data-lat"]
    if article.has_attr("data-lng"):
        data["longitude"] = article["data-lng"]

    name_link = article.select_one(".b-result__name a")
    if name_link:
        data["nom"] = name_link.get_text(strip=True)
        href = name_link.get("href", "")
        data["url"] = href.split("?")[0] if href else ""

    addr_p = article.select_one(".b-result__address p")
    if addr_p:
        lines = [l.strip() for l in addr_p.get_text("\n").split("\n") if l.strip()]
        if len(lines) >= 1:
            data["adresse"] = lines[0]
        if len(lines) >= 2:
            data["cp"] = lines[1]
        if len(lines) >= 3:
            data["ville"] = lines[2]

    phone_btn = article.select_one("button[data-protected-text]")
    if phone_btn:
        data["telephone"] = decode_phone(phone_btn.get("data-protected-text", ""))

    grade = article.select_one(".b-rating__grade")
    if grade:
        data["note"] = grade.get_text(strip=True).replace(",", ".")
    count = article.select_one(".b-rating__count")
    if count:
        m = re.search(r"\d+", count.get_text(strip=True))
        if m:
            data["nb_avis"] = m.group(0)

    return data


def main():
    session = requests.Session()
    results = []
    seen_urls = set()

    print("▶ Récupération de la première page…")
    first_page = fetch_results_page(session, 1)
    total = first_page.get("results", {}).get("total", 0)
    last_page = first_page.get("results", {}).get("last_page", 1)
    print(f"✓ {total} magasin(s) au total, sur {last_page} page(s)")

    pages_data = [first_page]
    for page in range(2, last_page + 1):
        time.sleep(REQUEST_DELAY)
        try:
            pages_data.append(fetch_results_page(session, page))
            print(f"  page {page}/{last_page} récupérée")
        except requests.RequestException as e:
            print(f"  ⚠ échec page {page} : {e}")
            continue

    for page_data in pages_data:
        items_html = page_data.get("results", {}).get("items", "")
        soup = BeautifulSoup(items_html, "html.parser")
        for article in soup.select("article.b-result"):
            store = parse_store_fragment(str(article))
            if not store["url"] or store["url"] in seen_urls:
                continue
            seen_urls.add(store["url"])
            results.append(store)

    print(f"✓ {len(results)} fiche(s) magasin extraite(s) (après déduplication)")

    if not results:
        print("OK : 0")
        return

    fieldnames = ["nom", "adresse", "cp", "ville", "telephone",
                  "note", "nb_avis", "latitude", "longitude", "url"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(results)

    print("OK :", len(results))


if __name__ == "__main__":
    main()
