"""
export_opticiens_conseils.py

Scraping des fiches boutiques Opticiens Conseils.
Utilise requests + BeautifulSoup (pas de Selenium).
Compatible Render free tier.
"""

import re
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd

OUTPUT = "opticiens_conseils.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

BASE = "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-"

# ─── Liste complète des 27 boutiques ─────────────────────────────────────────
BOUTIQUE_URLS = [
    # Île-de-France
    BASE + "antony",
    BASE + "belle-epine",
    BASE + "boulogne-billancourt",
    BASE + "bretigny-sur-orge",
    BASE + "cergy",
    BASE + "corbeil-essonnes",
    BASE + "evry",
    BASE + "flins-sur-seine",
    BASE + "les-ulis",
    BASE + "massy",
    BASE + "neuilly-sur-seine",
    BASE + "osny",
    BASE + "paris-rivoli",
    BASE + "plaisir",
    BASE + "ris-orangis",
    BASE + "sainte-genevieve-des-bois",
    BASE + "saint-germain-en-laye",
    BASE + "saint-quentin-en-yvelines",
    BASE + "savigny-sur-orge",
    BASE + "villabe",
    BASE + "villebon-sur-yvette",
    BASE + "villeneuve-la-garenne",
    BASE + "viry-chatillon",
    # Hors Île-de-France
    BASE + "barentin",
    BASE + "rouen-gros-horloge",
    BASE + "tours",
    BASE + "villeneuve-dascq",
]


# ---------------------------------------------------
# FORMAT TELEPHONE
# ---------------------------------------------------
def format_phone(phone):
    if not phone:
        return ""
    phone = re.sub(r"[^\d+]", "", str(phone))
    prefixes = ["+33", "+262", "+590", "+594", "+596", "+687", "+689"]
    for prefix in prefixes:
        if phone.startswith(prefix):
            phone = "0" + phone[len(prefix):]
            break
    digits = re.sub(r"\D", "", phone)
    if len(digits) % 2 == 0:
        return " ".join(digits[i:i+2] for i in range(0, len(digits), 2))
    return digits


# ---------------------------------------------------
# EXTRACTION DEPARTEMENT
# ---------------------------------------------------
def extract_department(cp):
    if not cp:
        return ""
    cp = str(cp).strip()
    if cp.startswith("20"):
        return "2A/2B"
    dom = ["971", "972", "973", "974", "975", "976"]
    if cp[:3] in dom:
        return cp[:3]
    return cp[:2]


# ---------------------------------------------------
# NETTOYAGE TEXTE
# ---------------------------------------------------
def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------
# EXTRACTION CP + VILLE depuis adresse brute
# ---------------------------------------------------
def parse_cp_ville(adresse):
    cp_match = re.search(r"\b(\d{5})\b", adresse)
    cp = cp_match.group(1) if cp_match else ""
    ville = ""
    if cp_match:
        avant_cp = adresse[:cp_match.start()].rstrip(", ")
        tokens = [t.strip() for t in avant_cp.split(",") if t.strip()]
        if tokens:
            ville = tokens[-1]
    return cp, ville


# ---------------------------------------------------
# SCRAPING
# ---------------------------------------------------
print(f"{len(BOUTIQUE_URLS)} boutiques à scraper")

session = requests.Session()
session.headers.update(HEADERS)

rows = []

for i, url in enumerate(BOUTIQUE_URLS, start=1):
    print(f"[{i}/{len(BOUTIQUE_URLS)}] {url}")

    try:
        response = session.get(url, timeout=20)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"  ⚠ Erreur réseau : {e}")
        rows.append({
            "url": url, "nom": "", "adresse": "",
            "cp": "", "ville": "", "departement": "",
            "telephone": "", "email": ""
        })
        continue

    soup = BeautifulSoup(response.text, "html.parser")

    data = {
        "url": url,
        "nom": "",
        "adresse": "",
        "cp": "",
        "ville": "",
        "departement": "",
        "telephone": "",
        "email": "",
    }

    # Nom
    h1 = soup.find("h1")
    if h1:
        data["nom"] = clean_text(h1.get_text())

    # Adresse (lien Google Maps)
    maps_link = soup.find(
        "a", href=lambda h: h and "google.com/maps" in h
    )
    if maps_link:
        raw_adresse = clean_text(maps_link.get_text(" "))
        data["adresse"] = raw_adresse
        cp, ville = parse_cp_ville(raw_adresse)
        data["cp"] = cp
        data["ville"] = ville
        data["departement"] = extract_department(cp)
    else:
        address_el = soup.select_one(".store-address-link p")
        if address_el:
            raw_adresse = clean_text(address_el.get_text(" "))
            data["adresse"] = raw_adresse
            cp, ville = parse_cp_ville(raw_adresse)
            data["cp"] = cp
            data["ville"] = ville
            data["departement"] = extract_department(cp)

    # Téléphone
    tel = soup.select_one('a[href^="tel:"]')
    if tel:
        raw_phone = tel.get("data-phone") or clean_text(tel.get_text())
        data["telephone"] = format_phone(raw_phone)

    # Email
    email = soup.select_one('a[href^="mailto:"]')
    if email:
        data["email"] = (
            email.get("data-email")
            or email.get("href", "").replace("mailto:", "").strip()
        )

    rows.append(data)
    time.sleep(0.3)


# ---------------------------------------------------
# EXPORT CSV
# ---------------------------------------------------
df = pd.DataFrame(rows)

print(f"\nTotal boutiques : {len(df)}")

df.to_csv(OUTPUT, sep=";", encoding="utf-8-sig", index=False)
print(f"CSV exporté : {OUTPUT}")