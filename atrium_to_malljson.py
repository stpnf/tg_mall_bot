import re
import json
import requests
from bs4 import BeautifulSoup
import time
import os

INPUT_FILE = 'files/атриум.txt'
OUTPUT_FILE = 'atrium_for_malls.json'

REQUEST_DELAY = 0.7

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    html = f.read()

pattern = re.compile(r'<a href="([^"]+/catalog/[^"]+/)"[^>]*>.*?<h4 class="item_title">(.*?)</h4>', re.DOTALL)
items = pattern.findall(html)

stores = {}

for url, name in items:
    name = name.strip()
    full_url = url if url.startswith('http') else f'https://www.atrium.su{url}'
    try:
        resp = requests.get(full_url, timeout=10, headers=headers)
        if resp.status_code != 200:
            floor = 'нет данных'
        else:
            soup = BeautifulSoup(resp.text, 'html.parser')
            floor_text = soup.get_text()
            # Улучшенная регулярка: ищет все числа перед "этаж" или "этаже"
            floor_matches = re.findall(r'([0-9]+)[-–]?(?:\s*и\s*[0-9]+)?\s*этаже?', floor_text, re.IGNORECASE)
            if floor_matches:
                floor = floor_matches[0]
            else:
                floor = 'нет данных'
                # debug: сохраняем html для анализа
                with open('debug_response.html', 'w', encoding='utf-8') as debug_file:
                    debug_file.write(resp.text)
                print(f"Сохранил debug_response.html для {name}")
                break
    except Exception as e:
        floor = 'нет данных'
    stores[name] = floor
    print(f'{name}: {floor}')
    time.sleep(REQUEST_DELAY)

output_dir = os.path.dirname(OUTPUT_FILE)
if output_dir and not os.path.exists(output_dir):
    os.makedirs(output_dir)

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(stores, f, ensure_ascii=False, indent=2)
print(f'Готово! Сохранено в {OUTPUT_FILE}') 