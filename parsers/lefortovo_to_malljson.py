import re
import json

INPUT_FILE = '../files/лефортово.txt'
OUTPUT_FILE = 'lefortovo_for_malls.json'

MALL_NAME = 'Город Лефортово'
ADDRESS = 'ш. Энтузиастов, 12, Москва'
MAP_LINK = 'https://yandex.ru/maps/org/gorod_lefortovo/1122334455/'
UNDERGROUND = ''
CITY = 'Москва'

def main():
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

    # Найти все карточки магазинов
    shop_blocks = re.findall(r'<div class="ttl">(.*?)</div>.*?<div class="lvl">(.*?)</div>', html, re.DOTALL)
    stores = {}
    for name, lvl_html in shop_blocks:
        name = name.strip()
        # Извлечь этаж
        floor_match = re.search(r'<b class="num">(.*?)</b>этаж', lvl_html)
        if floor_match:
            floor = floor_match.group(1).strip()
        else:
            floor = 'нет данных'
        stores[name] = floor

    mall_data = {
        MALL_NAME: {
            'address': ADDRESS,
            'map_link': MAP_LINK,
            'underground': UNDERGROUND,
            'stores': stores
        }
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(mall_data, f, ensure_ascii=False, indent=2)
    print(f'Готово! Сохранено в {OUTPUT_FILE}')

if __name__ == '__main__':
    main() 