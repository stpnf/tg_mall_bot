import re
import json
from bs4 import BeautifulSoup

# Пути к файлам
HTML_PATH = "files/колумсбус.txt"
MALLS_PATH = "malls.json"

# 1. Чтение HTML
with open(HTML_PATH, encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

# 2. Парсинг магазинов
stores = {}
for event in soup.find_all("div", class_="eventItem"):
    # Название
    title_div = event.find("div", class_="eventItem__title")
    if not title_div:
        continue
    name = title_div.get_text(strip=True)
    # Этаж
    scheme_link = event.find("a", class_="schemeLink")
    floor = None
    href = scheme_link.get("href") if scheme_link else None
    if href:
        m = re.search(r"floor=(\d+)", href)
        if m:
            floor = int(m.group(1))
    stores[name] = floor
    print(f"Магазин: {name}, этаж: {repr(floor)}, ссылка: {href}")

# 3. Чтение malls.json
with open(MALLS_PATH, encoding="utf-8") as f:
    malls = json.load(f)

# 4. Вставка в Columbus
malls["Москва"]["Columbus"]["stores"] = stores

# 5. Сохраняем
with open(MALLS_PATH, "w", encoding="utf-8") as f:
    json.dump(malls, f, ensure_ascii=False, indent=2)

print(f"Добавлено {len(stores)} магазинов в Columbus.") 