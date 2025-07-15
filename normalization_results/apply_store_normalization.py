import json
import shutil

# Пути к файлам
MALLS_PATH = 'malls.json'
MAP_PATH = 'normalization_results/store_group_map_normalized.json'
ALIASES_PATH = 'aliases.json'

# Резервная копия malls.json
shutil.copy2(MALLS_PATH, MALLS_PATH + '.bak')
print(f'Сделана резервная копия malls.json -> malls.json.bak')

# Загрузка маппинга
with open(MAP_PATH, encoding='utf-8') as f:
    store_map = json.load(f)

# Загрузка malls.json
with open(MALLS_PATH, encoding='utf-8') as f:
    malls = json.load(f)

# Заменяем все варианты на эталонные
for city, malls_in_city in malls.items():
    for mall_name, mall_data in malls_in_city.items():
        stores = mall_data.get('stores', {})
        new_stores = {}
        for store, value in stores.items():
            etalon = store_map.get(store, store)
            # Если уже есть такой магазин, не перезаписываем (или можно объединять значения)
            if etalon in new_stores:
                continue
            new_stores[etalon] = value
        mall_data['stores'] = new_stores

# Сохраняем malls.json
with open(MALLS_PATH, 'w', encoding='utf-8') as f:
    json.dump(malls, f, ensure_ascii=False, indent=2)
print('malls.json успешно нормализован!')

# (Опционально) Нормализация aliases.json
try:
    with open(ALIASES_PATH, encoding='utf-8') as f:
        aliases = json.load(f)
    new_aliases = {}
    for store, variants in aliases.items():
        etalon = store_map.get(store, store)
        # Собираем все варианты, приводим к эталону
        all_variants = set()
        for v in variants:
            all_variants.add(store_map.get(v, v))
        all_variants.add(etalon)
        new_aliases[etalon] = sorted(all_variants)
    with open(ALIASES_PATH, 'w', encoding='utf-8') as f:
        json.dump(new_aliases, f, ensure_ascii=False, indent=2)
    print('aliases.json также нормализован!')
except Exception as e:
    print('aliases.json не найден или не удалось обновить:', e) 