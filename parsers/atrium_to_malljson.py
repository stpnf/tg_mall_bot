import re
import json
import requests
from bs4 import BeautifulSoup
import time
import os

INPUT_FILE = '../files/атриум.txt'
OUTPUT_FILE = 'atrium_for_malls.json'

REQUEST_DELAY = 0.7

with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    html = f.read()

pattern = re.compile(r'<a href="([^"]+/catalog/[^"]+/)"[^>]*>.*?<h4 class="item_title">(.*?)</h4>', re.DOTALL)
items = pattern.findall(html)

stores = {}

for url, name in items:
    name = name.strip()
    full_url = url if url.startswith('http') else f'https://www.atrium.su{url}'
    try:
        resp = requests.get(full_url, timeout=10)
        if resp.status_code != 200:
            floor = 'нет данных'
        else:
            soup = BeautifulSoup(resp.text, 'html.parser')
            floor_text = soup.get_text()
            floor_match = re.search(r'на\s+([0-9]+)\s*этаже', floor_text, re.IGNORECASE)
            if floor_match:
                floor = floor_match.group(1)
            else:
                floor_match = re.search(r'на\s+([0-9]+)[^0-9]+этаже', floor_text, re.IGNORECASE)
                if floor_match:
                    floor = floor_match.group(1)
                else:
                    floor = 'нет данных'
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