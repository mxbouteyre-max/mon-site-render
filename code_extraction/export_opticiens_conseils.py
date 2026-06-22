"""
export_opticiens_conseils.py

Problème précédent : le wait.until() de l'étape 1 (collecte des URLs
depuis la carte Shopify) timeout sur Render car le store locator JS
ne se charge pas dans les temps côté serveur.

Solution : on récupère les URLs des boutiques depuis le sitemap Shopify
avec requests (pas de Selenium, pas de JS), ce qui est instantané et
fiable. Selenium n'est utilisé que pour le scraping des fiches
individuelles (nécessaire car le site retourne 403 à requests).
"""

import re
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

BASE_URL   = "https://www.opticienconseil.fr"
SITEMAP    = f"{BASE_URL}/sitemap.xml"
OUTPUT     = "opticiens_conseils.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

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


# ─────────────────────────────────────────────────────────────
# ÉTAPE 1 : Collecte des URLs via le sitemap (requests, pas Selenium)
# ─────────────────────────────────────────────────────────────

def get_boutique_urls() -> list[str]:
    """Lit le sitemap Shopify et extrait les URLs de boutiques."""
    session = requests.Session()
    session.headers.update(HEADERS)

    # Le sitemap principal pointe vers des sous-sitemaps
    r = session.get(SITEMAP, timeout=20)
    r.raise_for_status()

    urls = []
    root = ET.fromstring(r.text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    # Cherche d'abord les sous-sitemaps (sitemap index)
    sub_sitemaps = root.findall(".//sm:loc", ns)

    boutique_pattern = re.compile(r"/a/magasins/boutiques/")

    for loc in sub_sitemaps:
        loc_url = loc.text.strip()

        # Si c'est une URL de boutique directe
        if boutique_pattern.search(loc_url):
            urls.append(loc_url)
            continue

        # Si c'est un sous-sitemap, on le charge
        if "sitemap" in loc_url.lower() and loc_url.endswith(".xml"):
            try:
                sub = session.get(loc_url, timeout=20)
                sub_root = ET.fromstring(sub.text)
                for sub_loc in sub_root.findall(".//sm:loc", ns):
                    sub_url = sub_loc.text.strip()
                    if boutique_pattern.search(sub_url):
                        urls.append(sub_url)
            except Exception as e:
                print(f"  ⚠ Sous-sitemap ignoré ({loc_url}) : {e}")

    # Déduplique et nettoie
    urls = sorted(set(
        u.split("?")[0].split("#")[0] for u in urls
    ))
    return urls


# ─────────────────────────────────────────────────────────────
# ÉTAPE 2 : Scraping des fiches avec Selenium
# ─────────────────────────────────────────────────────────────

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


print("Étape 1 : collecte des URLs via le sitemap…")
links = get_boutique_urls()
print(f"→ {len(links)} boutiques trouvées")

if not links:
    print("❌ Aucune URL trouvée dans le sitemap.")
else:
    driver = make_driver()

    # Bloque les ressources inutiles via CDP
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": BLOCKED_DOMAINS})

    wait = WebDriverWait(driver, 20)
    rows = []

    print(f"Étape 2 : scraping des {len(links)} fiches…")

    try:
        for i, url in enumerate(links, start=1):
            print(f"[{i}/{len(links)}] {url}")

            try:
                driver.get(url)

                try:
                    wait.until(
                        EC.presence_of_element_located((By.TAG_NAME, "h1"))
                    )
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
                print(f"  ⚠ Erreur WebDriver : {e}")

    finally:
        driver.quit()

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT, sep=";", encoding="utf-8-sig", index=False)
    print(f"\nCSV généré : {OUTPUT}  ({len(df)} boutiques)")