from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import time

BASE_URL = "https://opticduroc.com/boutiques"

# -------------------------------------------------
# CONFIG SELENIUM
# -------------------------------------------------
options = Options()

# IMPORTANT :
# commente cette ligne si problème
# options.add_argument("--headless")

options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")

driver = webdriver.Chrome(options=options)

print("Ouverture du site...")
driver.get(BASE_URL)

# -------------------------------------------------
# Attendre que la page charge
# -------------------------------------------------
time.sleep(8)

# -------------------------------------------------
# Scroll progressif
# -------------------------------------------------
last_height = driver.execute_script("return document.body.scrollHeight")

for _ in range(15):

    driver.execute_script(
        "window.scrollTo(0, document.body.scrollHeight);"
    )

    time.sleep(2)

    new_height = driver.execute_script(
        "return document.body.scrollHeight"
    )

    if new_height == last_height:
        break

    last_height = new_height

# -------------------------------------------------
# DEBUG
# -------------------------------------------------
print("Titre page :", driver.title)

html = driver.page_source

# Sauvegarde debug
with open("debug_duroc.html", "w", encoding="utf-8") as f:
    f.write(html)

driver.quit()

# -------------------------------------------------
# PARSING
# -------------------------------------------------
soup = BeautifulSoup(html, "html.parser")

stores = soup.select("li[data-store-id]")

print(f"{len(stores)} boutiques trouvées.")

resultats = []

for store in stores:

    try:

        # -------------------------
        # NOM + URL
        # -------------------------
        nom = ""
        fiche_url = ""

        nom_tag = store.select_one("strong a")

        if nom_tag:
            nom = nom_tag.get_text(strip=True)
            fiche_url = urljoin(BASE_URL, nom_tag.get("href"))

        # -------------------------
        # ADRESSE
        # -------------------------
        street = store.select_one(".wpsl-street")
        city = store.select_one(".wpsl-city")
        country = store.select_one(".wpsl-country")

        adresse = " ".join(filter(None, [
            street.get_text(strip=True) if street else "",
            city.get_text(strip=True) if city else "",
            country.get_text(strip=True) if country else ""
        ]))

        # -------------------------
        # TELEPHONE
        # -------------------------
        telephone = ""

        tel_tag = store.select_one("a[href^='tel:']")

        if tel_tag:
            telephone = tel_tag.get_text(strip=True)

        # -------------------------
        # EMAIL
        # -------------------------
        email = ""

        contact_spans = store.select("p.wpsl-contact-details span")

        for span in contact_spans:

            text = span.get_text(" ", strip=True)

            if "@" in text:
                email = text.split(":")[-1].strip()

        # -------------------------
        # FAX
        # -------------------------
        fax = ""

        fax_tag = store.select_one(".store-fax")

        if fax_tag:

            fax_text = fax_tag.get_text(" ", strip=True)

            if ":" in fax_text:
                fax = fax_text.split(":")[-1].strip()

        # -------------------------
        # STORE ID
        # -------------------------
        store_id = ""

        id_tag = store.select_one(".id-store")

        if id_tag:
            store_id = id_tag.get_text(strip=True)

        resultats.append({
            "store_id": store_id,
            "nom": nom,
            "adresse": adresse,
            "telephone": telephone,
            "fax": fax,
            "email": email,
            "url_fiche": fiche_url
        })

    except Exception as e:
        print("Erreur :", e)

# -------------------------------------------------
# EXPORT CSV
# -------------------------------------------------
df = pd.DataFrame(resultats)

output_file = "optic_duroc_boutiques.csv"

df.to_csv(
    output_file,
    sep=";",
    index=False,
    encoding="utf-8-sig"
)

print(f"\nCSV sauvegardé : {output_file}")
print(df.head())