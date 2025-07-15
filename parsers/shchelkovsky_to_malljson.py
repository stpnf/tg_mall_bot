import re
import json
from bs4 import BeautifulSoup

HTML_PATH = "files/щелковский.txt"
MALLS_PATH = "malls.json"
MALL_KEY = "Щелковский"  # Как в malls.json
CITY_KEY = "Москва"

with open(HTML_PATH, encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

stores = {}
for a in soup.find_all("a", class_="card-name"):
    name = a.get_text(strip=True)
    floor = None
    # Ищем ближайший <small>... этаж</small> после <a>
    next_small = a.find_next("small")
    if next_small:
        m = re.search(r"(\d+) этаж", next_small.get_text())
        if m:
            floor = int(m.group(1))
    stores[name] = floor
    print(f"Магазин: {name}, этаж: {repr(floor)}")

with open(MALLS_PATH, encoding="utf-8") as f:
    malls = json.load(f)

# Если ТЦ еще нет, создаём
if MALL_KEY not in malls[CITY_KEY]:
    malls[CITY_KEY][MALL_KEY] = {"address": "", "map_link": "", "underground": "", "stores": {}}

malls[CITY_KEY][MALL_KEY]["stores"] = stores

with open(MALLS_PATH, "w", encoding="utf-8") as f:
    json.dump(malls, f, ensure_ascii=False, indent=2)

print(f"Добавлено {len(stores)} магазинов в {MALL_KEY}.") 