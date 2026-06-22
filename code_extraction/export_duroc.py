from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd

BASE_URL = "https://opticduroc.com/boutiques"

# -------------------------------------------------
# CONFIG SELENIUM
# -------------------------------------------------
options = Options()

# --headless=new est OBLIGATOIRE sur un serveur sans interface graphique
# (Render, etc.) : sans ça Chrome essaie d'ouvrir une fenêtre et plante
# au démarrage (SessionNotCreatedException). --no-sandbox et
# --disable-dev-shm-usage évitent d'autres plantages classiques en
# environnement conteneurisé.
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1400,2000")
options.add_argument("--disable-blink-features=AutomationControlled")

driver = webdriver.Chrome(options=options)

print("Ouverture du site...")
driver.get(BASE_URL)

# -------------------------------------------------
# Attendre que la liste des boutiques soit chargée
# -------------------------------------------------
# Le plugin WP Store Locator injecte les <li data-store-id="..."> en JS
# après coup (ils ne sont jamais présents dans le HTML source brut).
# On attend donc explicitement leur apparition, plutôt qu'une pause fixe
# arbitraire de 8 secondes qui peut être trop courte ou trop longue
# selon la latence du jour.
try:
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "li[data-store-id]"))
    )
except TimeoutException:
    print("⚠ La liste des boutiques n'est pas apparue après 20s — le site a peut-être changé.")

# -------------------------------------------------
# Scroll jusqu'à ce que toutes les boutiques soient chargées
# -------------------------------------------------
# On compare le nombre de <li data-store-id> trouvés plutôt que la
# hauteur de la page (plus fiable si le site charge par lots en AJAX
# au scroll) ; on s'arrête dès que ce nombre se stabilise sur deux
# scrolls consécutifs, sans attendre 2 secondes fixes à chaque fois.
def count_stores():
    return driver.execute_script(
        "return document.querySelectorAll('li[data-store-id]').length;"
    )

last_count = count_stores()
stable_rounds = 0
MAX_SCROLLS = 30

for _ in range(MAX_SCROLLS):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    try:
        WebDriverWait(driver, 3).until(
            lambda d: count_stores() > last_count
        )
        new_count = count_stores()
    except TimeoutException:
        # aucune nouvelle boutique chargée pendant ce scroll
        new_count = last_count

    if new_count == last_count:
        stable_rounds += 1
        if stable_rounds >= 2:
            break
    else:
        stable_rounds = 0

    last_count = new_count

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
        # STORE ID (identifiant unique du magasin)
        # -------------------------
        # C'est l'attribut data-store-id du <li> lui-même qui contient
        # le véritable identifiant. Le span ".id-store" du template du
        # site affiche en réalité le numéro de fax (bug du site, le
        # template Underscore.js le confirme : <span class="id-store">
        # <%= fax %></span>), donc on ne s'y fie pas pour l'identifiant.
        store_id = store.get("data-store-id", "")

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
