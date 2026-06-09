from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import csv

# ⚙️ mode headless (optionnel)
options = Options()
options.add_argument("--headless=new")

driver = webdriver.Chrome(options=options)

url = "URL_DE_TA_PAGE"
driver.get(url)

time.sleep(5)  # laisse le JS charger

results = []

# 🔍 récupérer tous les blocs magasins
cards = driver.find_elements(By.CLASS_NAME, "b-result__address-phone-status")

for card in cards:
    try:
        # 📍 adresse
        address = card.find_element(By.CLASS_NAME, "b-result__address").text

        # 📞 téléphone (si déchiffré par JS)
        try:
            phone_button = card.find_element(By.TAG_NAME, "button")
            phone = phone_button.text.strip()
        except:
            phone = None

        results.append([address, phone])

    except Exception as e:
        continue

driver.quit()

# 💾 CSV
with open("magasins.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow(["Adresse", "Téléphone"])
    writer.writerows(results)

print("OK :", len(results))