import json

MALLS_PATH = "malls.json"
CITY = "Санкт-Петербург"
MALL = "Галерея"
STORE = "Шоколадница"

with open(MALLS_PATH, encoding="utf-8") as f:
    malls = json.load(f)

found = False
floor = None
if CITY in malls and MALL in malls[CITY]:
    stores = malls[CITY][MALL]["stores"]
    for name, fl in stores.items():
        if name.strip().lower() == STORE.lower():
            found = True
            floor = fl
            break

if found:
    print(f"✅ Магазин '{STORE}' найден в '{MALL}' ({CITY}), этаж: {floor}")
else:
    print(f"❌ Магазин '{STORE}' НЕ найден в '{MALL}' ({CITY})") 