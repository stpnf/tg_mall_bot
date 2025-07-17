import json
import re
from rapidfuzz import process, fuzz

# Загрузка всех уникальных магазинов
MALLS_PATH = '../malls.json'

with open(MALLS_PATH, encoding='utf-8') as f:
    malls = json.load(f)

all_stores = set()
def extract_stores(malls):
    for key, value in malls.items():
        if isinstance(value, dict) and 'stores' in value:
            all_stores.update(value['stores'])
        elif isinstance(value, dict):
            for mall in value.values():
                if isinstance(mall, dict) and 'stores' in mall:
                    all_stores.update(mall['stores'])
extract_stores(malls)
all_stores = [s for s in all_stores if s.strip()]

def normalize_name(name):
    words = re.sub(r'[^a-zA-Z0-9а-яА-Я ]', '', name).lower().split()
    return ' '.join(sorted(words))

# Группировка по нормализованному виду
norm_groups = {}
for store in all_stores:
    norm = normalize_name(store)
    norm_groups.setdefault(norm, []).append(store)

def choose_etalon(group):
    def score(name):
        return (
            name[0].isupper(),
            -sum(1 for c in name if c in '«»"'),
            -len(name),
            name
        )
    return sorted(group, key=score, reverse=True)[0]

norm_group_map = {}
for group in norm_groups.values():
    etalon = choose_etalon(group)
    for variant in group:
        norm_group_map[variant] = etalon

with open('store_groups_normalized.json', 'w', encoding='utf-8') as f:
    json.dump(list(norm_groups.values()), f, ensure_ascii=False, indent=2)
with open('store_group_map_normalized.json', 'w', encoding='utf-8') as f:
    json.dump(norm_group_map, f, ensure_ascii=False, indent=2)

# Найти топ-20 спорных случаев (различие только в регистре или одной букве)
ambiguous = []
for group in norm_groups.values():
    if len(group) > 1:
        for i in range(len(group)):
            for j in range(i+1, len(group)):
                a, b = group[i], group[j]
                if a.lower() == b.lower() or fuzz.ratio(a, b) >= 95:
                    ambiguous.append({"group": group, "pair": [a, b]})

with open('ambiguous_groups_preview.json', 'w', encoding='utf-8') as f:
    json.dump(ambiguous[:20], f, ensure_ascii=False, indent=2)

print('Группировка по нормализованному виду завершена. Пример групп:')
print(list(norm_groups.values())[:5])
print('Пример маппинга:')
print(list(norm_group_map.items())[:10])
print('Топ-20 спорных случаев сохранены в ambiguous_groups_preview.json') 