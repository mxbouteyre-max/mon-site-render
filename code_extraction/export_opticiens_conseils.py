"""
export_opticiens_conseils.py

Le sitemap Shopify n'inclut pas les pages /a/magasins/boutiques/ (pages
d'app tierces exclues), et la carte JS ne se charge pas sur Render.

Solution : liste des URLs hardcodée (réseau de ~30 boutiques, stable).
Selenium scrape uniquement les fiches individuelles.
Pour ajouter une boutique : ajouter son URL dans BOUTIQUE_URLS.
"""

import re
from bs4 import BeautifulSoup
import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

OUTPUT = "opticiens_conseils.csv"

# ─── Liste des boutiques (à compléter si nouvelles ouvertures) ────────────────
BOUTIQUE_URLS = [
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-evry",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-sainte-genevieve-des-bois",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-ris-orangis",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-les-ulis",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-bretigny-sur-orge",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-osny",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-corbeil-essonnes",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-massy",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-neuilly-sur-seine",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-saint-quentin-en-yvelines",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-belle-epine",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-villabe",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-boulogne-billancourt",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-antony",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-plaisir",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-savigny-sur-orge",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-tours",
    "https://www.opticienconseil.fr/a/magasins/boutiques/les-opticiens-conseils-villeneuve-la-garenne",
]

BLOCKED_DOMAINS = [
    "*cdn.shopify.com*",
    "*cdn-gkefn.nitrocdn.com*",
    "*googletagmanager.com*",
    "*google-analytics.com*",
    "*facebook.net*",
    "*hotjar.com*",
]


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def make_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option(
        "prefs", {"profile.managed_default_content_settings.images": 2}
    )
    return webdriver.Chrome(options=options)


print(f"{len(BOUTIQUE_URLS)} boutiques à scraper")

driver = make_driver()
driver.execute_cdp_cmd("Network.enable", {})
driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": BLOCKED_DOMAINS})
wait = WebDriverWait(driver, 20)
rows = []

try:
    for i, url in enumerate(BOUTIQUE_URLS, start=1):
        print(f"[{i}/{len(BOUTIQUE_URLS)}] {url}")

        try:
            driver.get(url)

            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
            except TimeoutException:
                print(f"  ⚠ Timeout sur {url}, on continue")

            soup = BeautifulSoup(driver.page_source, "html.parser")

            data = {"url": url, "nom": "", "adresse": "", "telephone": "", "email": ""}

            h1 = soup.find("h1")
            if h1:
                data["nom"] = clean_text(h1.get_text())

            maps_link = soup.find("a", href=lambda h: h and "google.com/maps/dir" in h)
            if maps_link:
                data["adresse"] = clean_text(maps_link.get_text(" "))
            else:
                address = soup.select_one(".store-address-link p")
                if address:
                    data["adresse"] = clean_text(address.get_text(" "))

            tel = soup.select_one('a[href^="tel:"]')
            if tel:
                data["telephone"] = tel.get("data-phone") or clean_text(tel.get_text())

            email = soup.select_one('a[href^="mailto:"]')
            if email:
                data["email"] = (
                    email.get("data-email")
                    or email.get("href", "").replace("mailto:", "").strip()
                )

            rows.append(data)

        except WebDriverException as e:
            print(f"  ⚠ Erreur : {e}")

finally:
    driver.quit()

df = pd.DataFrame(rows)
df.to_csv(OUTPUT, sep=";", encoding="utf-8-sig", index=False)
print(f"\nCSV généré : {OUTPUT}  ({len(df)} boutiques)")