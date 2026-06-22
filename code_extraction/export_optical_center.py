"""
export_optical_center.py

Le script original utilisait Playwright qui ne peut pas fonctionner sur
Render (binaire Chromium absent, `playwright install` non exécuté).

Découverte clé : le store locator d'Optical Center est hébergé sur un
sous-domaine séparé (opticien.optical-center.fr) en HTML statique paginé
accessible directement avec requests — aucun navigateur n'est nécessaire.

Structure : https://opticien.optical-center.fr/fr?page=N
  → 41 pages × ~20 magasins = 807 magasins en France

Approche : requests + BeautifulSoup (parsing HTML) + ThreadPoolExecutor
(téléchargement parallèle des 41 pages) — léger en mémoire, rapide.
"""

import csv
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, fields, astuple
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_URL   = "https://opticien.optical-center.fr"
LIST_URL   = f"{BASE_URL}/fr"
OUTPUT_CSV = "optical_center_boutiques.csv"
MAX_PAGES  = 50   # plafond de sécurité ; on s'arrête dès qu'une page est vide
MAX_WORKERS = 10  # pages téléchargées en parallèle

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── Modèle ─────────────────────────────────────────────────────────────────────

@dataclass
class Boutique:
    nom:          Optional[str]
    adresse:      Optional[str]
    code_postal:  Optional[str]
    ville:        Optional[str]
    telephone:    Optional[str]
    statut:       Optional[str]
    type_service: Optional[str]
    url_fiche:    Optional[str]
    url_maps:     Optional[str]

# ── Session HTTP par thread ────────────────────────────────────────────────────

_thread_local = threading.local()

def get_session() -> requests.Session:
    if not hasattr(_thread_local, "session"):
        s = requests.Session()
        s.headers.update(HEADERS)
        _thread_local.session = s
    return _thread_local.session

# ── Parsing d'une page ─────────────────────────────────────────────────────────

def parse_page(html: str) -> list[Boutique]:
    soup = BeautifulSoup(html, "html.parser")
    boutiques = []

    # Chaque magasin est dans un <li> qui contient un <h2> avec le nom
    for li in soup.select("li"):
        h2 = li.select_one("h2")
        if not h2:
            continue
        nom = h2.get_text(strip=True)
        if not nom:
            continue

        # URL fiche
        lien = li.select_one("a[href^='/'][href*='-optical-center']")
        url_fiche = (BASE_URL + lien["href"]) if lien else None

        # Adresse — le texte brut du <li>, on nettoie
        # Structure : nom / adresse ligne 1 / adresse ligne 2 (opt) / CP ville
        # On reconstruit depuis les lignes de texte du <li>
        raw_lines = []
        for child in li.children:
            text = child.get_text(" ", strip=True) if hasattr(child, "get_text") else str(child).strip()
            if text and text != nom:
                raw_lines.append(text)

        # Extraction CP + ville depuis le texte brut
        adresse_full = " ".join(raw_lines)
        cp_match = re.search(
            r"\b(\d{5})\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ '\-]*?)(?=\s*(?:Ouvert|Fermé|Optique|Service|$))",
            adresse_full
        )
        code_postal = cp_match.group(1) if cp_match else None
        ville_raw   = cp_match.group(2).strip() if cp_match else None

        # Adresse = tout ce qui précède le CP dans le texte non-h2 du <li>
        # On prend les spans ou paragraphes d'adresse explicitement
        adresse_parts = []
        # Cherche les blocs texte avant le CP
        if cp_match and cp_match.group(1):
            before_cp = adresse_full[:adresse_full.find(cp_match.group(1))].strip()
            # Nettoie les fragments de l'UI (labels, "Appuyer sur...", etc.)
            before_cp = re.sub(r"Appuyer sur.*?informations", "", before_cp, flags=re.DOTALL)
            before_cp = re.sub(r"Prendre rendez-vous", "", before_cp)
            before_cp = re.sub(r"Point de vente\s*:", "", before_cp)
            before_cp = re.sub(r"\s+", " ", before_cp).strip()
            # Retire le nom du magasin s'il s'est glissé dedans
            before_cp = before_cp.replace(nom, "").strip()
            adresse_parts = [before_cp] if before_cp else []

        adresse = " | ".join(filter(None, adresse_parts)) or None

        # Téléphone
        tel_tag = li.select_one("a[href^='tel:']")
        telephone = None
        if tel_tag:
            telephone = tel_tag.get_text(strip=True)

        # URL Google Maps
        maps_tag = li.select_one("a[href*='google.com/maps']")
        url_maps = maps_tag["href"] if maps_tag else None

        # Statut (Ouvert / Fermé) et type de service
        # Ces informations sont en texte libre dans le <li>
        full_text = li.get_text(" ", strip=True)
        statut = None
        if re.search(r"\bOuvert\b", full_text):
            m = re.search(r"(Ouvert[^|]*?)(?:\s{2,}|Optique|Service)", full_text)
            statut = m.group(1).strip() if m else "Ouvert"
        elif re.search(r"\bFermé\b", full_text):
            statut = "Fermé"

        type_service = None
        for t in ["Optique & Audition", "Service à domicile", "Optique"]:
            if t in full_text:
                type_service = t
                break

        boutiques.append(Boutique(
            nom=nom,
            adresse=adresse,
            code_postal=code_postal,
            ville=ville_raw,
            telephone=telephone,
            statut=statut,
            type_service=type_service,
            url_fiche=url_fiche,
            url_maps=url_maps,
        ))

    return boutiques


# ── Téléchargement d'une page ──────────────────────────────────────────────────

def fetch_page(page_num: int) -> tuple[int, list[Boutique]]:
    """Télécharge et parse une page. Retourne (page_num, boutiques)."""
    session = get_session()
    url = f"{LIST_URL}?page={page_num}"
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        boutiques = parse_page(r.text)
        return page_num, boutiques
    except Exception as e:
        print(f"  ⚠ Erreur page {page_num} : {e}")
        return page_num, []


# ── Détection du nombre de pages ──────────────────────────────────────────────

def get_total_pages() -> int:
    """Récupère le nombre total de pages.

    La pagination HTML ne montre que 5 liens à la fois (pages N+/-2),
    donc chercher le max des liens visibles retournerait au plus 5
    -> ~100 boutiques au lieu de 807. On cherche "1 sur 41" dans le
    texte de la pagination, avec MAX_PAGES comme valeur de repli.
    """
    session = get_session()
    try:
        r = session.get(f"{LIST_URL}?page=1", timeout=20)
        r.raise_for_status()
        text = BeautifulSoup(r.text, "html.parser").get_text()
        # "1 sur 41" dans la pagination
        m = re.search(r"\bsur\s+(\d+)", text)
        if m:
            return int(m.group(1))
        # Repli : total magasins / 20 (arrondi au sup)
        m2 = re.search(r"(\d+)\s+magasins", text)
        if m2:
            return -(-int(m2.group(1)) // 20)
    except Exception:
        pass
    return MAX_PAGES


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    print("Détection du nombre de pages…")
    total_pages = get_total_pages()
    print(f"→ {total_pages} pages détectées")

    all_boutiques: list[Boutique] = []
    seen_urls: set[str] = set()  # déduplication par URL fiche

    print(f"Téléchargement des {total_pages} pages ({MAX_WORKERS} en parallèle)…")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(fetch_page, p): p
            for p in range(1, total_pages + 1)
        }
        for future in as_completed(futures):
            page_num, boutiques = future.result()
            new = 0
            for b in boutiques:
                key = b.url_fiche or b.nom
                if key and key not in seen_urls:
                    seen_urls.add(key)
                    all_boutiques.append(b)
                    new += 1
            print(f"  Page {page_num:3d} → {len(boutiques):2d} boutiques "
                  f"({new} nouvelles) | total : {len(all_boutiques)}")

    print(f"\n{'='*50}")
    print(f"Total : {len(all_boutiques)} boutiques uniques")

    if not all_boutiques:
        print("❌ Aucune boutique récupérée.")
        return

    # Export CSV
    col_names = [f.name for f in fields(Boutique)]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";", quoting=csv.QUOTE_ALL)
        writer.writerow(col_names)
        for b in all_boutiques:
            writer.writerow(astuple(b))

    print(f"✅ CSV : {OUTPUT_CSV}")


if __name__ == "__main__":
    main()