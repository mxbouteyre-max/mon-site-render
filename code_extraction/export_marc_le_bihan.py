import requests
from bs4 import BeautifulSoup
import pandas as pd

# URL du site
url = "https://www.marclebihan.fr/magasins"

# Headers pour éviter certains blocages
headers = {
    "User-Agent": "Mozilla/5.0"
}

# Récupération du HTML
response = requests.get(url, headers=headers)

# Vérification
if response.status_code != 200:
    print("Erreur lors de la récupération du site")
    exit()

# Parsing HTML
soup = BeautifulSoup(response.text, "html.parser")

# Tous les magasins
stores = soup.find_all("article", class_="store-item")

# Liste des résultats
data = []

for store in stores:
    
    # Nom
    name_tag = store.find("p", class_="card-title")
    name = name_tag.text.strip() if name_tag else None

    # Adresse
    address_tag = store.find("address")
    address = address_tag.text.strip() if address_tag else None

    # Téléphone
    phone_tag = store.find("p", class_="phone-number")
    phone = phone_tag.text.strip() if phone_tag else None

    # Image
    img_tag = store.find("img")
    image = img_tag["src"] if img_tag else None

    # Lien
    link_tag = store.find("a", class_="link")
    link = link_tag["href"] if link_tag else None

    # Si le lien est relatif → on ajoute le domaine
    if link and not link.startswith("http"):
        link = "https://www.marclebihan.fr/" + link

    # Ajout dans la liste
    data.append({
        "nom": name,
        "adresse": address,
        "telephone": phone,
        "image": image,
        "lien": link
    })

# DataFrame pandas
df = pd.DataFrame(data)

# Affichage
print(df)

# Sauvegarde CSV
df.to_csv("magasins_marclebihan.csv", index=False, encoding="utf-8-sig")

print("\nCSV sauvegardé : magasins_marclebihan.csv")