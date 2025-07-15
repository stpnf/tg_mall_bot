import re
import json
from bs4 import BeautifulSoup

HTML_PATH = "files/МЕГА Дыбенко.html"
MALLS_PATH = "malls.json"
MALL_KEY = "МЕГА Дыбенко"  # Как в malls.json
CITY_KEY = "Санкт-Петербург"

with open(HTML_PATH, encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

stores = {}
for item in soup.find_all("article", class_="card-shop"):
    name_span = item.find("span", class_="card-shop__heading-link")
    floor_p = item.find("p", class_="card-shop__floor")
    categories_ul = item.find("ul", class_="card-shop__categories")
    if name_span and floor_p:
        name = name_span.get_text(strip=True)
        floor_text = floor_p.get_text(strip=True)
        m = re.search(r"(-?\d+) этаж", floor_text)
        floor = int(m.group(1)) if m else None
        categories = []
        if categories_ul:
            categories = [li.get_text(strip=True) for li in categories_ul.find_all("li")]
        stores[name] = {"floor": floor, "categories": categories}
        print(f"Магазин: {name}, этаж: {floor}, категории: {categories}")

# Чтение malls.json
with open(MALLS_PATH, encoding="utf-8") as f:
    malls = json.load(f)

# Добавление или обновление ТЦ "МЕГА Дыбенко"
if MALL_KEY not in malls:
    malls[MALL_KEY] = {
        "address": "",
        "map_link": "",
        "underground": "",
        "stores": {}
    }
for name, data in stores.items():
    malls[MALL_KEY]["stores"][name] = data["floor"]  # Для совместимости с текущей структурой
    # Если нужно сохранить категории, можно добавить их в отдельный словарь или расширить структуру

# Сохраняем malls.json
with open(MALLS_PATH, "w", encoding="utf-8") as f:
    json.dump(malls, f, ensure_ascii=False, indent=2)

print(f"Добавлено {len(stores)} магазинов в МЕГА Дыбенко") 