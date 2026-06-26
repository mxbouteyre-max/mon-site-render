import requests
import csv
import time
import re
from bs4 import BeautifulSoup


def extract_city_department(address):
    city = ""
    cp = ""
    departement = ""

    match = re.search(r"(\d{5})\s+(.+)", address)

    if match:
        cp = match.group(1)
        city = match.group(2).strip()
        departement = cp[:2]

    return city, cp, departement


def scrape_ecouter_voir(
    query="Paris, France",
    lat=48.8575475,
    lng=2.3513765
):
    base_url = "https://magasins.ecoutervoir.fr/resultats"
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

        response = requests.get(base_url, params=params, headers=headers)

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
        articles = soup.find_all("article", class_="b-result")

        if not articles:
            print("Aucune boutique trouvée")
            break

        for article in articles:
            store = extract_store_info(article)
            if store:
                all_stores.append(store)

        current_page = data.get("results", {}).get("current_page", 1)
        last_page = data.get("results", {}).get("last_page", 1)

        print(f"Page {current_page}/{last_page} - {len(articles)} boutiques")

        if current_page >= last_page:
            break

        page += 1
        time.sleep(0.5)

    return all_stores


def extract_store_info(article):
    try:
        # Nom
        title_tag = article.find("h2", class_="b-result__title")
        nom = title_tag.get_text(strip=True) if title_tag else ""

        # Adresse
        address_tag = article.find("p", class_="b-result__address")
        adresse = " ".join(address_tag.stripped_strings) if address_tag else ""

        # Ville / CP / Département
        ville, cp, departement = extract_city_department(adresse)

        # Téléphone
        phone_link = article.find("a", href=lambda h: h and h.startswith("tel:"))
        if phone_link:
            telephone = (
                phone_link["href"]
                .replace("tel:", "")
                .replace("+33", "0")
            )
        else:
            telephone = ""

        # Coordonnées GPS
        latitude = article.get("data-lat", "")
        longitude = article.get("data-lng", "")

        # URL
        link_tag = article.find("a", class_="b-result__link")
        if link_tag and link_tag.get("href"):
            url = link_tag["href"]
            if url.startswith("/"):
                url = "https://magasins.ecoutervoir.fr" + url
        else:
            url = ""

        return {
            "nom":         nom,
            "adresse":     adresse,
            "cp":          cp,
            "ville":       ville,
            "departement": departement,
            "telephone":   telephone,
            "latitude":    latitude,
            "longitude":   longitude,
            "url":         url,
        }

    except Exception as e:
        print(f"Erreur extraction : {e}")
        return None


def save_to_csv(stores, filename="ecouter_voir_boutiques.csv"):
    if not stores:
        print("Aucune boutique à sauvegarder")
        return

    fieldnames = [
        "nom",
        "adresse",
        "cp",
        "ville",
        "departement",
        "telephone",
        "latitude",
        "longitude",
        "url",
    ]

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(stores)

    print(f"{len(stores)} boutiques sauvegardées dans {filename}")


if __name__ == "__main__":
    stores = scrape_ecouter_voir()
    save_to_csv(stores)