import requests
import csv
import time
import re
from bs4 import BeautifulSoup


def extract_city_department(address):
    """
    Extrait :
    - code postal
    - ville
    - département
    depuis une adresse française
    """

    city = ""
    postal_code = ""
    department = ""

    match = re.search(r"(\d{5})\s+(.+)", address)

    if match:
        postal_code = match.group(1)
        city = match.group(2).strip()
        department = postal_code[:2]

    return city, postal_code, department


def scrape_ecouter_voir(
    query="Paris, France",
    lat=48.8575475,
    lng=2.3513765
):
    """
    Scrape les boutiques Écouter Voir
    """

    base_url = "https://magasins.ecoutervoir.fr/resultats"

    # Zone Paris
    bounds = "48.8155622,2.2242171,48.9021476,2.4698511"

    all_stores = []

    page = 1

    while True:

        params = {
            "q": query,
            "p": f"{lat},{lng}",
            "s": "geocoder",
            "b": bounds,
            "__xhr": "1",
            "page": page
        }

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest"
        }

        response = requests.get(
            base_url,
            params=params,
            headers=headers
        )

        if response.status_code != 200:
            print(f"Erreur {response.status_code} page {page}")
            break

        try:
            data = response.json()

        except Exception as e:
            print("Erreur JSON :", e)
            print(response.text[:500])
            break

        html_content = data.get("results", {}).get("items", "")

        if not html_content:
            print("Plus de résultats")
            break

        soup = BeautifulSoup(html_content, "html.parser")

        articles = soup.find_all(
            "article",
            class_="b-result"
        )

        if not articles:
            print("Aucune boutique trouvée")
            break

        for article in articles:

            store = extract_store_info(article)

            if store:
                all_stores.append(store)

        current_page = data.get(
            "results",
            {}
        ).get(
            "current_page",
            1
        )

        last_page = data.get(
            "results",
            {}
        ).get(
            "last_page",
            1
        )

        print(
            f"Page {current_page}/{last_page}"
            f" - {len(articles)} boutiques"
        )

        if current_page >= last_page:
            break

        page += 1

        time.sleep(0.5)

    return all_stores


def extract_store_info(article):
    """
    Extrait les informations d'une boutique
    """

    try:

        # Nom
        title_tag = article.find(
            "h2",
            class_="b-result__title"
        )

        name = (
            title_tag.get_text(strip=True)
            if title_tag else ""
        )

        # Adresse
        address_tag = article.find(
            "p",
            class_="b-result__address"
        )

        if address_tag:
            address = " ".join(
                address_tag.stripped_strings
            )

        else:
            address = ""

        # Ville / CP / Département
        city, postal_code, department = (
            extract_city_department(address)
        )

        # Téléphone
        phone_link = article.find(
            "a",
            href=lambda h: h and h.startswith("tel:")
        )

        if phone_link:

            phone = (
                phone_link["href"]
                .replace("tel:", "")
                .replace("+33", "0")
            )

        else:
            phone = ""

        # Note
        rating_tag = article.find(
            "div",
            class_="b-rating__grade"
        )

        rating = (
            rating_tag.get_text(strip=True)
            if rating_tag else ""
        )

        # Coordonnées GPS
        lat = article.get("data-lat", "")
        lng = article.get("data-lng", "")

        # URL fiche magasin
        link_tag = article.find(
            "a",
            class_="b-result__link"
        )

        if link_tag and link_tag.get("href"):

            store_url = link_tag["href"]

            if store_url.startswith("/"):

                store_url = (
                    "https://magasins.ecoutervoir.fr"
                    + store_url
                )

        else:
            store_url = ""

        return {
            "nom": name,
            "adresse": address,
            "code_postal": postal_code,
            "ville": city,
            "departement": department,
            "telephone": phone,
            "note": rating,
            "latitude": lat,
            "longitude": lng,
            "url_magasin": store_url
        }

    except Exception as e:

        print(f"Erreur extraction : {e}")

        return None


def save_to_csv(
    stores,
    filename="ecouter_voir_boutiques.csv"
):
    """
    Sauvegarde dans un CSV propre
    """

    if not stores:
        print("Aucune boutique à sauvegarder")
        return

    fieldnames = [
        "nom",
        "adresse",
        "code_postal",
        "ville",
        "departement",
        "telephone",
        "note",
        "latitude",
        "longitude",
        "url_magasin"
    ]

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter=";"
        )

        writer.writeheader()

        writer.writerows(stores)

    print(
        f"{len(stores)} boutiques sauvegardées "
        f"dans {filename}"
    )


if __name__ == "__main__":

    stores = scrape_ecouter_voir()

    save_to_csv(stores)