from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup
import pandas as pd
import time
import re


START_URL = "https://www.opticienconseil.fr/a/magasins"


def clean_text(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip()


# -----------------------------
# SELENIUM
# -----------------------------

chrome_options = Options()
chrome_options.add_argument("--headless=new")

driver = webdriver.Chrome(options=chrome_options)

wait = WebDriverWait(driver, 20)


# -----------------------------
# RECUP URLS BOUTIQUES
# -----------------------------

driver.get(START_URL)

wait.until(
    EC.presence_of_element_located(
        (By.CSS_SELECTOR, 'a[href*="/a/magasins/boutiques/"]')
    )
)

time.sleep(3)

links_elements = driver.find_elements(
    By.CSS_SELECTOR,
    'a[href*="/a/magasins/boutiques/"]'
)

links = set()

for el in links_elements:
    href = el.get_attribute("href")

    if href:
        href = href.split("?")[0].split("#")[0]
        links.add(href)

links = sorted(list(links))

print(f"{len(links)} boutiques trouvées")


# -----------------------------
# SCRAPING BOUTIQUES
# -----------------------------

rows = []

for i, url in enumerate(links, start=1):

    print(f"[{i}/{len(links)}] {url}")

    try:

        driver.get(url)

        wait.until(
            EC.presence_of_element_located(
                (By.TAG_NAME, "h1")
            )
        )

        time.sleep(1)

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

        # ADRESSE
        address = soup.select_one(".store-address-link p")

        if address:
            data["adresse"] = clean_text(
                address.get_text(" ")
            )

        # TEL
        tel = soup.select_one('a[href^="tel:"]')

        if tel:
            data["telephone"] = (
                tel.get("data-phone")
                or tel.get_text(strip=True)
            )

        # EMAIL
        email = soup.select_one('a[href^="mailto:"]')

        if email:
            data["email"] = (
                email.get("data-email")
                or email.get("href").replace("mailto:", "")
            )

        rows.append(data)

    except Exception as e:
        print(f"Erreur : {e}")


driver.quit()


# -----------------------------
# EXPORT CSV
# -----------------------------

df = pd.DataFrame(rows)

df.to_csv(
    "opticiens_conseils.csv",
    sep=";",
    encoding="utf-8-sig",
    index=False
)

print("CSV généré : opticiens_conseils.csv")