"""
export_opticiens_conseils.py

Le site opticienconseil.fr retourne 403 aux requêtes HTTP directes
(protection Cloudflare/Shopify) — Selenium reste nécessaire pour tout
le script. En revanche les optimisations apportées sont :

  - Options Chrome corrigées pour Render (--headless=new, --no-sandbox,
    --disable-dev-shm-usage) → corrige le crash TimeoutError
  - time.sleep(3) et time.sleep(1) fixes supprimés, remplacés par des
    WebDriverWait sur les éléments réellement attendus
  - driver.quit() dans un bloc finally pour garantir la libération
    mémoire même en cas d'erreur
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

BASE_URL = "https://www.opticienconseil.fr"
START_URL = f"{BASE_URL}/a/magasins"
OUTPUT = "opticiens_conseils.csv"


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def make_driver():
    options = Options()
    # Indispensable sur Render (pas d'interface graphique)
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return webdriver.Chrome(options=options)


driver = make_driver()
wait = WebDriverWait(driver, 20)

try:
    # ─────────────────────────────────────────────────────────
    # ÉTAPE 1 : Collecte des URLs de boutiques
    # ─────────────────────────────────────────────────────────
    print("Ouverture de la page boutiques…")
    driver.get(START_URL)

    # Attente explicite des liens plutôt que sleep fixe
    try:
        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'a[href*="/a/magasins/boutiques/"]')
            )
        )
    except TimeoutException:
        print("⚠ Timeout : aucun lien de boutique trouvé après 20s.")

    links = set()
    for el in driver.find_elements(
        By.CSS_SELECTOR, 'a[href*="/a/magasins/boutiques/"]'
    ):
        href = el.get_attribute("href")
        if href:
            href = href.split("?")[0].split("#")[0]
            links.add(href)

    links = sorted(links)
    print(f"{len(links)} boutiques trouvées")

    # ─────────────────────────────────────────────────────────
    # ÉTAPE 2 : Scraping de chaque fiche
    # ─────────────────────────────────────────────────────────
    rows = []

    for i, url in enumerate(links, start=1):
        print(f"[{i}/{len(links)}] {url}")

        try:
            driver.get(url)

            # Attente du h1 plutôt que sleep fixe de 1s
            try:
                wait.until(
                    EC.presence_of_element_located((By.TAG_NAME, "h1"))
                )
            except TimeoutException:
                print(f"  ⚠ Timeout sur {url}, on continue")

            soup = BeautifulSoup(driver.page_source, "html.parser")

            data = {
                "url": url,
                "nom": "",
                "adresse": "",
                "telephone": "",
                "email": "",
            }

            # NOM
            h1 = soup.find("h1")
            if h1:
                data["nom"] = clean_text(h1.get_text())

            # ADRESSE — lien Google Maps en priorité (contient l'adresse
            # complète avec CP), sinon bloc .store-address-link
            maps_link = soup.find(
                "a", href=lambda h: h and "google.com/maps/dir" in h
            )
            if maps_link:
                data["adresse"] = clean_text(maps_link.get_text(" "))
            else:
                address = soup.select_one(".store-address-link p")
                if address:
                    data["adresse"] = clean_text(address.get_text(" "))

            # TELEPHONE
            tel = soup.select_one('a[href^="tel:"]')
            if tel:
                data["telephone"] = (
                    tel.get("data-phone")
                    or clean_text(tel.get_text())
                )

            # EMAIL
            email = soup.select_one('a[href^="mailto:"]')
            if email:
                data["email"] = (
                    email.get("data-email")
                    or email.get("href", "").replace("mailto:", "").strip()
                )

            rows.append(data)

        except WebDriverException as e:
            print(f"  ⚠ Erreur WebDriver : {e}")

finally:
    # Libère Chrome et sa mémoire dans tous les cas
    driver.quit()

# ─────────────────────────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────────────────────────
df = pd.DataFrame(rows)

df.to_csv(
    OUTPUT,
    sep=";",
    encoding="utf-8-sig",
    index=False
)

print(f"\nCSV généré : {OUTPUT}  ({len(df)} boutiques)")
