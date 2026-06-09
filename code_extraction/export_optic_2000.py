import requests
from bs4 import BeautifulSoup
import csv
import math
import time
import re

BASE_URL = "https://opticien.optic2000.com/resultats"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest"
}

def clean(text):
    return " ".join(text.split()) if text else None


# 📍 EXTRACTION LOCALISATION
def extract_location(address):
    if not address:
        return None, None, None

    match = re.search(r"\b(\d{5})\b", address)

    postal_code = match.group(1) if match else None
    city = None
    department = None

    if postal_code:
        department = postal_code[:2]

        parts = address.split(postal_code)
        if len(parts) > 1:
            city = clean(parts[1])

    return postal_code, city, department


# 📞 FORMATAGE TÉLÉPHONE
def format_phone(phone):
    if not phone:
        return None

    phone = phone.replace("tel:", "").replace("+33", "").replace(" ", "")
    
    # force 10 chiffres
    phone = phone.zfill(10)

    return " ".join([phone[i:i+2] for i in range(0, 10, 2)])


def fetch_page(page):
    params = {
        "q": "Paris",
        "p": "48.8575,2.3513",
        "b": "48.81,2.22,48.90,2.46",
        "page": page,
        "__xhr": 1
    }

    res = requests.get(BASE_URL, params=params, headers=HEADERS)
    res.raise_for_status()

    data = res.json()
    return data["results"]["items"], data["results"]["total"], data["results"]["per_page"]


def parse_items(html):
    soup = BeautifulSoup(html, "html.parser")

    stores = []

    for article in soup.select("article.b-result"):

        # Nom
        name_el = article.select_one(".b-result__title")
        name = clean(name_el.get_text()) if name_el else None

        # Adresse
        addr_el = article.select_one(".b-result__address")
        address = clean(addr_el.get_text(" ")) if addr_el else None

        # Téléphone brut
        phone_el = article.select_one("a[href^='tel:']")
        phone = phone_el["href"] if phone_el else None
        phone = format_phone(phone)

        # URL magasin
        url_el = article.select_one("a.b-result__link")
        url = url_el["href"] if url_el else None

        # 📍 extraction ville / CP / département
        postal_code, city, department = extract_location(address)

        stores.append({
            "name": name,
            "address": address,
            "postal_code": postal_code,
            "city": city,
            "department": department,
            "phone": phone,
            "url": url
        })

    return stores


def main():
    all_stores = []

    html, total, per_page = fetch_page(1)
    total_pages = math.ceil(total / per_page)

    print(f"Total magasins: {total} → {total_pages} pages")

    all_stores.extend(parse_items(html))

    for page in range(2, total_pages + 1):
        print(f"Page {page}/{total_pages}")

        try:
            html, _, _ = fetch_page(page)
            all_stores.extend(parse_items(html))

        except Exception as e:
            print("Erreur page", page, e)
            break

        time.sleep(1)


    # 📦 EXPORT CSV PROPRE
    filename = "optic2000_all_enriched.csv"

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "name",
                "address",
                "postal_code",
                "city",
                "department",
                "phone",
                "url"
            ],
            delimiter=";"
        )
        writer.writeheader()
        writer.writerows(all_stores)

    print(f"\nTerminé ✔ {len(all_stores)} magasins exportés")


if __name__ == "__main__":
    main()