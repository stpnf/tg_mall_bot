import json
from rapidfuzz import fuzz, process
import itertools

# Пути к файлам
MAP_PATH = 'store_group_map_normalized.json'
ALIASES_OUT = 'smart_aliases.json'

# Список популярных сокращений и прозвищ для топ-брендов (можно расширять)
MANUAL_BRAND_ALIASES = {
    'New Balance': ['Нью Баланс', 'нб', 'NB'],
    'Nike': ['Найк', 'nike', 'найк'],
    'Adidas': ['Адик', 'адик', 'adidas'],
    'Reebok': ['Рибок', 'рибок', 'reebok'],
    'Puma': ['Пума', 'пума', 'puma'],
    'MAAG': ['Мааг', 'мааг', 'маг'],
    'Zara': ['Зара', 'зара', 'zara'],
    'H&M': ['HM', 'H and M', 'эйчэм'],
    'Uniqlo': ['Юникло', 'юникло', 'uniqlo'],
    'Lacoste': ['Лакост', 'лакост', 'lacoste'],
    'Levi’s': ['Левайс', 'левайс', 'levis'],
    'Pull&Bear': ['Пул энд Бир', 'пулбир', 'пул энд бер'],
    'Bershka': ['Бершка', 'бершка', 'bershka'],
    'Stradivarius': ['Страдивариус', 'страдивариус', 'stradivarius'],
    'Tommy Hilfiger': ['Томми', 'томми', 'hilfiger'],
    'Calvin Klein': ['Кельвин', 'кельвин', 'ck'],
    'Under Armour': ['Андер', 'андер', 'UA'],
    'Vans': ['Ванс', 'ванс', 'vans'],
    'Converse': ['Конверс', 'конверс', 'converse'],
    'Crocs': ['Крокс', 'крокс', 'crocs'],
    'Columbia': ['Коламбия', 'коламбия', 'columbia'],
    'The North Face': ['Норт Фейс', 'нортфейс', 'tnf'],
    'Timberland': ['Тимбер', 'тимбер', 'timberland'],
    'Gucci': ['Гуччи', 'гуччи', 'gucci'],
    'Louis Vuitton': ['Луи', 'луи', 'lv'],
    'Chanel': ['Шанель', 'шанель', 'chanel'],
    'Prada': ['Прада', 'прада', 'prada'],
    'Hermes': ['Гермес', 'гермес', 'hermes'],
    'Fendi': ['Фенди', 'фенди', 'fendi'],
    'Versace': ['Версаче', 'версаче', 'versace'],
    'Balenciaga': ['Баленсиага', 'баленсиага', 'balenciaga'],
    'Moncler': ['Монклер', 'монклер', 'moncler'],
    'Supreme': ['Суприм', 'суприм', 'supreme'],
    'Stone Island': ['Стоник', 'стоник', 'stone'],
}

# Генерация вероятных опечаток (1 переставленная буква, 1 пропущенная буква)
def typo_variants(name):
    variants = set()
    # Перестановка двух соседних букв
    for i in range(len(name)-1):
        swapped = list(name)
        swapped[i], swapped[i+1] = swapped[i+1], swapped[i]
        variants.add(''.join(swapped))
    # Пропущенная буква
    for i in range(len(name)):
        variants.add(name[:i] + name[i+1:])
    # Только варианты, отличающиеся от оригинала и не слишком короткие
    return {v for v in variants if v != name and len(v) >= max(3, len(name)-2)}

# Загрузка эталонов
with open(MAP_PATH, encoding='utf-8') as f:
    group_map = json.load(f)

# Собираем уникальные эталоны
etalons = sorted(set(group_map.values()))

aliases = {}
for etalon in etalons:
    variants = set()
    variants.add(etalon)
    # Добавляем вариант с другим регистром (если отличается)
    if etalon.lower() != etalon:
        variants.add(etalon.lower())
    # Добавляем вероятные опечатки
    for typo in itertools.islice(typo_variants(etalon), 2):
        variants.add(typo)
    # Добавляем ручные прозвища для топ-брендов
    if etalon in MANUAL_BRAND_ALIASES:
        for v in MANUAL_BRAND_ALIASES[etalon]:
            variants.add(v)
    # Оставляем не более 4 уникальных вариантов
    aliases[etalon] = sorted(list(variants))[:4]

with open(ALIASES_OUT, 'w', encoding='utf-8') as f:
    json.dump(aliases, f, ensure_ascii=False, indent=2)

print('Сгенерированы "умные" алиасы. Примеры:')
for k, v in list(aliases.items())[:10]:
    print(f'{k}: {v}') 