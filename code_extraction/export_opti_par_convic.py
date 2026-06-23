import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re

BASE = "https://www.opticiensparconviction.fr"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

all_shops = []
seen = set()


def get_soup(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)

        print(f"URL = {url}")
        print(f"STATUS = {r.status_code}")

        if r.status_code != 200:
            return None

        return BeautifulSoup(r.text, "html.parser")

    except Exception as e:
        print("ERROR:", e)
        return None


def extract_shops_from_page(url):

    soup = get_soup(url)

    if not soup:
        return []

    shops = []

    # liens de la page
    links = soup.find_all("a")

    print("LINKS =", len(links))

    # récupération téléphone
    for i, a in enumerate(links):

        href = a.get("href", "")
        text = a.get_text(" ", strip=True)

        if "/votre-opticien" not in href:
            continue

        if not text:
            continue

        # téléphone = lien suivant
        phone = ""

        if i + 1 < len(links):

            nxt = links[i + 1]
            nxt_href = nxt.get("href", "")

            if nxt_href.startswith("tel:"):
                phone = nxt_href.replace("tel:", "").strip()

        # URL complète
        shop_url = href

        if shop_url.startswith("/"):
            shop_url = BASE + shop_url

        # récupération bloc HTML proche
        parent = a.parent

        html = parent.get_text(" ", strip=True)

        # CP
        zipcode = ""

        cp_match = re.search(r"\b\d{5}\b", html)

        if cp_match:
            zipcode = cp_match.group(0)

        # ville
        city = ""

        if zipcode:
            city = html.split(zipcode)[-1].strip()

        # GPS
        lat = ""
        lng = ""
        code = ""

        span = parent.find_previous("span", attrs={"data-lat": True})

        if span:

            lat = span.get("data-lat", "")
            lng = span.get("data-lng", "")
            code = span.get("data-code", "")

        shop = {
            "nom": text,
            "telephone": phone,
            "url": shop_url,
            "cp": zipcode,
            "ville": city,
            "latitude": lat,
            "longitude": lng,
            "code": code,
        }

        shops.append(shop)

    print("FOUND =", len(shops))

    return shops


def get_city_pages():

    url = f"{BASE}/trouver-un-opticien/opticien-a-paris?esv=1"

    soup = get_soup(url)

    if not soup:
        return []

    city_urls = set()

    for a in soup.find_all("a", href=True):

        href = a["href"]

        if "/trouver-un-opticien/opticien-a-" in href:

            if href.startswith("/"):
                href = BASE + href

            city_urls.add(href)

    print("CITY URLS FOUND =", len(city_urls))

    return list(city_urls)


def save_csv():

    df = pd.DataFrame(all_shops)

    df.to_csv(
        "opticiens_par_conviction.csv",
        index=False,
        encoding="utf-8-sig"
    )

    print("\nCSV SAVED")


def main():

    city_pages = get_city_pages()

    print("\nTOTAL CITY PAGES =", len(city_pages))

    for idx, url in enumerate(city_pages):

        print("\n======================")
        print(f"[{idx+1}/{len(city_pages)}]")

        shops = extract_shops_from_page(url)

        new_count = 0

        for shop in shops:

            # doublons
            unique_key = shop["code"]

            if not unique_key:
                unique_key = f'{shop["name"]}_{shop["phone"]}'

            if unique_key in seen:
                continue

            seen.add(unique_key)

            all_shops.append(shop)

            new_count += 1

            print(
                f'NEW => {shop["name"]} | {shop["phone"]}'
            )

        print("NEW SHOPS =", new_count)

        save_csv()

        time.sleep(1)

    print("\n======================")
    print("TOTAL SHOPS =", len(all_shops))
    print("DONE")


if __name__ == "__main__":
    main()