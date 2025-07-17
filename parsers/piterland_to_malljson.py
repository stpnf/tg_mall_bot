import json
import re
from bs4 import BeautifulSoup

HTML_PATH = "files/питерлэнд.html"
MALLS_PATH = "malls.json"
MALL_KEY = "Питерлэнд"
CITY_KEY = "Санкт-Петербург"

with open(HTML_PATH, encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

stores = {}
for item in soup.find_all("div", class_="shops-list__item"):
    name_tag = item.find("img", class_="shop-card__img")
    if not name_tag:
        # Иногда название в .shop-card__pic-text
        name_tag = item.find("div", class_="shop-card__pic-text")
    if name_tag:
        name = name_tag.get("alt") if name_tag.has_attr("alt") else name_tag.get_text(strip=True)
    else:
        continue
    floor_tag = item.find("div", class_="shop-card__floor")
    if floor_tag:
        floor_text = floor_tag.get_text(strip=True)
        m = re.search(r"(-?\d+) этаж", floor_text)
        floor = int(m.group(1)) if m else None
    else:
        floor = None
    stores[name] = {"floor": floor}
    print(f"Магазин: {name}, этаж: {floor}")

# Чтение malls.json
with open(MALLS_PATH, encoding="utf-8") as f:
    malls = json.load(f)

# Добавление или обновление ТЦ "Питерлэнд"
if MALL_KEY not in malls:
    malls[MALL_KEY] = {
        "address": "",
        "map_link": "",
        "underground": "",
        "stores": {}
    }
for name, data in stores.items():
    malls[MALL_KEY]["stores"][name] = data["floor"]

# Сохраняем malls.json
with open(MALLS_PATH, "w", encoding="utf-8") as f:
    json.dump(malls, f, ensure_ascii=False, indent=2)

print(f"Добавлено {len(stores)} магазинов в Питерлэнд") 