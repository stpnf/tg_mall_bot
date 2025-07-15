import re
import json
from bs4 import BeautifulSoup
import os

def parse_vegas_floor(html_file_path, floor_num):
    with open(html_file_path, 'r', encoding='utf-8') as file:
        html_content = file.read()
    soup = BeautifulSoup(html_content, 'html.parser')
    stores = set()
    for a in soup.find_all('a'):
        name = a.get_text(strip=True)
        if name and len(name) > 1 and not re.search(r'этаж|карта|схема|магазин|vegas', name, re.I):
            stores.add(name)
    return stores

def parse_all_floors():
    base_dir = os.path.join(os.path.dirname(__file__), '../Для парсера/Вегас')
    store_floors = {}
    for floor in range(0, 5):
        fname = f'Вегас {floor} этаж.html'
        path = os.path.join(base_dir, fname)
        stores = parse_vegas_floor(path, floor)
        for store in stores:
            if store not in store_floors:
                store_floors[store] = []
            store_floors[store].append(floor)
    # Преобразуем: если этаж один — просто число, если несколько — список
    result = {}
    for store, floors in store_floors.items():
        if len(floors) == 1:
            result[store] = floors[0]
        else:
            result[store] = sorted(list(set(floors)))
    return result

def main():
    stores = parse_all_floors()
    with open('vegas_kuntsevo_stores_for_malls.json', 'w', encoding='utf-8') as f:
        json.dump(stores, f, ensure_ascii=False, indent=2)
    print('Готово! Сгенерирован блок для malls.json (vegas_kuntsevo_stores_for_malls.json)')

if __name__ == '__main__':
    main() 