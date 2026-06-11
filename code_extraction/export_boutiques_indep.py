#importation des librairies nécessaires au code pour tourner
import requests
from bs4 import BeautifulSoup
import json
import csv
import time
import urllib.parse

headers = {
    "User-Agent": "Mozilla/5.0"
}
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

#objet qui stocke le tableau des résultats obtenus

results = []

for dep in departements:

    encoded_dep = urllib.parse.quote_plus(dep)

# sélectionne et remplace dans encoded_dep la valeur du tableau dep définie plus haut, lance la boucle avec ce dep dans l'url et stocke les résultats dans le tableau result.

    BASE_URL = f"https://www.monopticien.com/trouvez-nous/6?ville={encoded_dep}"

#affiche dans le terminal quel département est scrapé

    print(f"\nScraping département : {dep}")

# boucle qui parcourt toutes les pages de la recherche associée au département dep dans la boucle précédente. Cette nouvelle boucle récupère sur les pages les données json relatives aux différentes boutiques. Ces données sont stockées dans des variables temporaires qui elles ensuite sont stockées dans une fonction result.append.

    for page in range(1, 20):

        print(f"Page {page}")

        url = BASE_URL + f"&page={page}"
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        scripts = soup.find_all("script", type="application/ld+json")

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

                results.append([
                    name,
                    street,
                    city,
                    postal,
                    dept_num,
                    phone,
                    url_site,
                    dep
                ])

            except Exception:
                continue

        time.sleep(1)

#affiche le nombre total de boutique récupérée lors de la session.

print("TOTAL :", len(results))

# CSV. Récupère les résultats et les range dans un classeur excel, avec comme séparateur ; (cf. delimiter=";")
with open("opticiens_france_et_outre.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f, delimiter=";")

    writer.writerow([
        "Nom",
        "Rue",
        "Ville",
        "CP",
        "Département",
        "Téléphone",
        "Site",
        "Zone recherchée"
    ])

    writer.writerows(results)

print("CSV généré ✔️")