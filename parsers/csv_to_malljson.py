import csv
import json
import sys
import os

# Настройки
CSV_FILE = '../files/__________________________________.csv'  # путь к исходному CSV
OUTPUT_FILE = 'paveletskaya_from_csv.json'  # выходной JSON

# Данные о ТЦ (можно скорректировать при необходимости)
MALL_NAME = 'Павелецкая Плаза'
ADDRESS = 'Павелецкая площадь, 3'
MAP_LINK = 'https://yandex.ru/maps/org/paveletskaya_plaza/72900666552/?indoorLevel=1&ll=37.639958%2C55.731014&z=17.17'
UNDERGROUND = ''
CITY = 'Москва'

def main():
    stores = {}
    with open(CSV_FILE, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            name = row['name'].strip()
            floor = row['floor'].strip()
            # Преобразуем этаж в int, если возможно
            try:
                floor_val = int(floor)
            except Exception:
                floor_val = floor
            stores[name] = floor_val

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