import re
import json
from bs4 import BeautifulSoup

HTML_PATH = "files/галерея.html"
MALLS_PATH = "malls.json"
MALL_KEY = "Галерея"  # Как в malls.json
CITY_KEY = "Санкт-Петербург"

with open(HTML_PATH, encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

stores = {}
for item in soup.find_all("div", class_="page-content__item shop"):
    name_div = item.find("div", class_="shop__header")
    floor_div = item.find("div", class_="shop__floor")
    if name_div and floor_div:
        name = name_div.get_text(strip=True)
        floor_text = floor_div.get_text(strip=True)
        m = re.search(r"(-?\d+) этаж", floor_text)
        floor = int(m.group(1)) if m else None
        stores[name] = floor
        print(f"Магазин: {name}, этаж: {floor}")

# Чтение malls.json
with open(MALLS_PATH, encoding="utf-8") as f:
    malls = json.load(f)

# Добавление или обновление ТЦ "Галерея"
if MALL_KEY not in malls:
    malls[MALL_KEY] = {
        "address": "",
        "map_link": "",
        "underground": "",
        "stores": {}
    }
malls[MALL_KEY]["stores"].update(stores)

# Сохраняем malls.json
with open(MALLS_PATH, "w", encoding="utf-8") as f:
    json.dump(malls, f, ensure_ascii=False, indent=2)

print(f"Добавлено {len(stores)} магазинов в Галерея") 