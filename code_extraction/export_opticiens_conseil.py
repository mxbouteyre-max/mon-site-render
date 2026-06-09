import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from webdriver_manager.chrome import ChromeDriverManager

# =========================================================
# CONFIG
# =========================================================

LIST_URL = "https://www.opticienconseil.fr/a/magasins"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

OUTPUT_FILE = "opticiens_conseils.csv"

# =========================================================
# SELENIUM SETUP
# =========================================================

options = Options()

# Mode sans fenêtre
options.add_argument("--headless=new")

options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)

# =========================================================
# 1. OUVERTURE PAGE LISTE
# =========================================================

print("Ouverture de la page magasins...")

driver.get(LIST_URL)

# Attente chargement JS
time.sleep(5)

# =========================================================
# 2. RECUPERATION DES URLS BOUTIQUES
# =========================================================

boutique_links = set()

elements = driver.find_elements(By.TAG_NAME, "a")

for el in elements:

    href = el.get_attribute("href")

    if href and "/a/magasins/boutiques/" in href:
        boutique_links.add(href)

driver.quit()

boutique_links = sorted(list(boutique_links))

print(f"{len(boutique_links)} boutiques trouvées")

# =========================================================
# 3. SCRAPING DES PAGES BOUTIQUES
# =========================================================

all_data = []

for url in boutique_links:

    print(f"Scraping : {url}")

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        scripts = soup.find_all(
            "script",
            type="application/ld+json"
        )

        target_json = None

        for script in scripts:

            try:

                if not script.string:
                    continue

                data = json.loads(script.string)

                if (
                    isinstance(data, dict)
                    and data.get("@type") == "Optician"
                ):
                    target_json = data
                    break

            except Exception:
                continue

        if not target_json:
            print("JSON-LD non trouvé")
            continue

        address = target_json.get("address", {})
        geo = target_json.get("geo", {})

        row = {
            "name": target_json.get("name"),
            "description": target_json.get("description"),
            "image": target_json.get("image"),
            "url": target_json.get("url"),

            "streetAddress": address.get("streetAddress"),
            "addressLocality": address.get("addressLocality"),
            "addressRegion": address.get("addressRegion"),
            "postalCode": address.get("postalCode"),
            "addressCountry": address.get("addressCountry"),

            "latitude": geo.get("latitude"),
            "longitude": geo.get("longitude"),

            "telephone": target_json.get("telephone")
        }

        all_data.append(row)

    except Exception as e:
        print(f"Erreur : {e}")

# =========================================================
# 4. EXPORT CSV
# =========================================================

df = pd.DataFrame(all_data)

df.to_csv(
    OUTPUT_FILE,
    sep=";",
    index=False,
    encoding="utf-8-sig"
)

print(f"\nCSV généré : {OUTPUT_FILE}")
print(f"{len(df)} boutiques exportées")