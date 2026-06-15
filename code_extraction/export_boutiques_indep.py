#importation des librairies nécessaires au code pour tourner
import requests
from bs4 import BeautifulSoup
import json
import csv
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

headers = {
    "User-Agent": "Mozilla/5.0"
}

# nombre de départements traités en parallèle (I/O-bound -> peut être > nb de coeurs)
MAX_WORKERS = 8

# pause entre deux requêtes successives faites par UN même worker (politesse serveur)
SLEEP_BETWEEN_PAGES = 0.5

# sécurité : on arrête de paginer un département dès qu'une page est vide,
# mais on garde une limite haute au cas où
MAX_PAGES = 20

#liste des départements utilisés dans l'URL
departements = [
"AIN (01)",
"AISNE (02)",
"ALLIER (03)",
"ALPES-DE-HAUTE-PROVENCE (04)",
"HAUTES-ALPES (05)",
"ALPES-MARITIMES (06)",
"ARDECHE (07)",
"ARDENNES (08)",
"ARIEGE (09)",
"AUBE (10)",
"AUDE (11)",
"AVEYRON (12)",
"BOUCHES-DU-RHONE (13)",
"CALVADOS (14)",
"CANTAL (15)",
"CHARENTE (16)",
"CHARENTE-MARITIME (17)",
"CHER (18)",
"CORREZE (19)",
"CORSE (20)",
"COTE-D'OR (21)",
"COTES-D'ARMOR (22)",
"CREUSE (23)",
"DORDOGNE (24)",
"DOUBS (25)",
"DROME (26)",
"EURE (27)",
"EURE-ET-LOIR (28)",
"FINISTERE (29)",
"GARD (30)",
"HAUTE-GARONNE (31)",
"GERS (32)",
"GIRONDE (33)",
"HERAULT (34)",
"ILLE-ET-VILAINE (35)",
"INDRE (36)",
"INDRE-ET-LOIRE (37)",
"ISERE (38)",
"JURA (39)",
"LANDES (40)",
"LOIR-ET-CHER (41)",
"LOIRE (42)",
"HAUTE-LOIRE (43)",
"LOIRE-ATLANTIQUE (44)",
"LOIRET (45)",
"LOT (46)",
"LOT-ET-GARONNE (47)",
"LOZERE (48)",
"MAINE-ET-LOIRE (49)",
"MANCHE (50)",
"MARNE (51)",
"HAUTE-MARNE (52)",
"MAYENNE (53)",
"MEURTHE-ET-MOSELLE (54)",
"MEUSE (55)",
"MORBIHAN (56)",
"MOSELLE (57)",
"NIEVRE (58)",
"NORD (59)",
"OISE (60)",
"ORNE (61)",
"PAS-DE-CALAIS (62)",
"PUY-DE-DOME (63)",
"PYRENEES-ATLANTIQUES (64)",
"HAUTES-PYRENEES (65)",
"PYRENEES-ORIENTALES (66)",
"BAS-RHIN (67)",
"HAUT-RHIN (68)",
"RHONE (69)",
"HAUTE-SAONE (70)",
"SAONE-ET-LOIRE (71)",
"SARTHE (72)",
"SAVOIE (73)",
"HAUTE-SAVOIE (74)",
"PARIS (75)",
"SEINE-MARITIME (76)",
"SEINE-ET-MARNE (77)",
"YVELINES (78)",
"DEUX-SEVRES (79)",
"SOMME (80)",
"TARN (81)",
"TARN-ET-GARONNE (82)",
"VAR (83)",
"VAUCLUSE (84)",
"VENDEE (85)",
"VIENNE (86)",
"HAUTE-VIENNE (87)",
"VOSGES (88)",
"YONNE (89)",
"TERRITOIRE DE BELFORT (90)",
"ESSONNE (91)",
"HAUTS-DE-SEINE (92)",
"SEINE-SAINT-DENIS (93)",
"VAL-DE-MARNE (94)",
"VAL-D'OISE (95)",
"GUADELOUPE (971)",
"MARTINIQUE (972)",
"GUYANE (973)",
"LA REUNION (974)",
"MAYOTTE (976)"
]


def scrape_departement(dep):
    """Scrape toutes les pages d'un département, s'arrête dès qu'une page est vide."""
    encoded_dep = urllib.parse.quote_plus(dep)
    BASE_URL = f"https://www.monopticien.com/trouvez-nous/6?ville={encoded_dep}"

    dep_results = []
    print(f"\nScraping département : {dep}")

    for page in range(1, MAX_PAGES + 1):
        url = BASE_URL + f"&page={page}"

        try:
            response = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")
            scripts = soup.find_all("script", type="application/ld+json")
        except Exception as e:
            print(f"  [{dep}] page {page} -> erreur réseau ({e}), arrêt du département")
            break

        page_count = 0
        for script in scripts:
            try:
                data = json.loads(script.string)

                if data.get("@type") != "Optician":
                    continue

                name = data.get("name")

                address = data.get("address", {})
                street = address.get("streetAddress")
                city = address.get("addressLocality")
                postal = address.get("postalCode")

                phone = data.get("telephone")
                url_site = data.get("url")

                dept_num = postal[:2] if postal else None

                dep_results.append([
                    name,
                    street,
                    city,
                    postal,
                    dept_num,
                    phone,
                    url_site,
                    dep
                ])
                page_count += 1

            except Exception:
                continue

        print(f"  [{dep}] page {page} -> {page_count} boutique(s)")

        # plus aucun résultat sur cette page -> on arrête de paginer ce département
        if page_count == 0:
            break

        time.sleep(SLEEP_BETWEEN_PAGES)

    return dep_results


results = []

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(scrape_departement, dep): dep for dep in departements}

    for future in as_completed(futures):
        dep = futures[future]
        try:
            dep_results = future.result()
            results.extend(dep_results)
        except Exception as e:
            print(f"Erreur sur le département {dep} : {e}")

print("\nTOTAL :", len(results))

# CSV. Récupère les résultats et les range dans un classeur excel, avec comme séparateur ; (cf. delimiter=";")
with open("opticiens_france_et_outre.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f, delimiter=";")

    writer.writerow([
        "nom",
        "adresse",
        "ville",
        "cp",
        "departement",
        "téléphone",
        "url",
        "Zone recherchée"
    ])

    writer.writerows(results)

print("CSV généré ✔️")