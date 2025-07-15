import re
import json
from bs4 import BeautifulSoup

HTML_PATH = "files/океания.html"
MALLS_PATH = "malls.json"
MALL_KEY = "Океания"  # Как в malls.json
CITY_KEY = "Москва"

with open(HTML_PATH, encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

stores = {}
for h3 in soup.find_all("h3", class_="text-center"):
    name = h3.get_text(strip=True)
    floor = None
    # Ищем ближайший <div class="item-floor ...">Этаж: N</div> после <h3>
    floor_div = h3.find_next("div", class_="item-floor")
    if floor_div:
        m = re.search(r"Этаж: (\d+)", floor_div.get_text())
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