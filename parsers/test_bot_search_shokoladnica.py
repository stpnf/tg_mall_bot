import json

MALLS_PATH = "malls.json"
CITY = "Санкт-Петербург"
STORE_QUERY = "Шоколадница"

with open(MALLS_PATH, encoding="utf-8") as f:
    malls = json.load(f)

results = []
for mall_name, mall_data in malls[CITY].items():
    stores = mall_data.get("stores", {})
    for name, floor in stores.items():
        if name.strip().lower() == STORE_QUERY.lower():
            results.append((mall_name, mall_data["address"], name, floor))

if results:
    print(f"✅ Найдено {len(results)} совпадений для '{STORE_QUERY}' в '{CITY}':")
    for mall, address, name, floor in results:
        print(f"  - {mall} ({address}): {name}, этаж: {floor}")
else:
    print(f"❌ Магазин '{STORE_QUERY}' не найден ни в одном ТЦ города '{CITY}'") 