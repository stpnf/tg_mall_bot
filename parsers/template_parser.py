"""
Шаблон парсера для торговых центров
Используйте этот файл как основу для создания новых парсеров
"""

import re
import json
from bs4 import BeautifulSoup

def parse_mall_stores(html_file_path):
    """
    Основная функция парсинга магазинов
    
    Args:
        html_file_path (str): Путь к HTML файлу с данными ТЦ
    
    Returns:
        dict: Словарь с данными магазинов
    """
    
    # Читаем HTML файл
    with open(html_file_path, 'r', encoding='utf-8') as file:
        html_content = file.read()
    
    # Парсим HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # TODO: Настройте селекторы под конкретный ТЦ
    # Пример для 2GIS:
    store_entries = soup.find_all('div', class_='_1kf6gff')
    
    stores = {}
    
    for entry in store_entries:
        # TODO: Настройте извлечение названия магазина
        name_link = entry.find('a', class_='_1rehek')
        if not name_link:
            continue
            
        name_span = name_link.find('span', class_='_lvwrwt')
        if not name_span:
            continue
            
        store_name = name_span.get_text(strip=True)
        store_name = re.sub(r'\s+', ' ', store_name).strip()
        
        if not store_name:
            continue
        
        # TODO: Настройте извлечение этажа
        floor_div = entry.find('div', class_='_klarpw')
        floor_num = 1  # По умолчанию
        
        if floor_div:
            floor_text = floor_div.get_text(strip=True)
            floor_match = re.search(r'(\d+)\s*этаж', floor_text)
            if floor_match:
                floor_num = int(floor_match.group(1))
        
        stores[store_name] = floor_num
    
    return stores

def format_mall_data(mall_name, stores, address, map_link, underground):
    """
    Форматирует данные для malls.json
    
    Args:
        mall_name (str): Название торгового центра
        stores (dict): Словарь магазинов
        address (str): Адрес ТЦ
        map_link (str): Ссылка на карту
        underground (str): Информация о метро
    
    Returns:
        dict: Структурированные данные ТЦ
    """
    
    mall_data = {
        mall_name: {
            "address": address,
            "map_link": map_link,
            "underground": underground,
            "stores": stores
        }
    }
    
    return mall_data

def save_results(mall_data, output_file):
    """
    Сохраняет результаты в JSON файл
    
    Args:
        mall_data (dict): Данные ТЦ
        output_file (str): Путь к выходному файлу
    """
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(mall_data, f, ensure_ascii=False, indent=2)
    
    print(f"Данные сохранены в {output_file}")

def main():
    """
    Пример использования парсера
    """
    
    # TODO: Настройте параметры под конкретный ТЦ
    html_file = "example_mall.txt"  # Путь к HTML файлу
    mall_name = "Название ТЦ"
    address = "Адрес ТЦ"
    map_link = "https://yandex.ru/maps/..."
    underground = "Ⓜ️Станция | 🚶 X мин | 🚌 Y мин"
    output_file = "example_mall_stores.json"
    
    print(f"Парсинг {mall_name}...")
    
    # Парсим магазины
    stores = parse_mall_stores(html_file)
    
    print(f"Найдено {len(stores)} магазинов")
    
    # Группируем по этажам для отображения
    floors = {}
    for store_name, floor_num in stores.items():
        if floor_num not in floors:
            floors[floor_num] = []
        floors[floor_num].append(store_name)
    
    for floor_num in sorted(floors.keys()):
        print(f"{floor_num} этаж: {len(floors[floor_num])} магазинов")
    
    # Форматируем данные
    mall_data = format_mall_data(mall_name, stores, address, map_link, underground)
    
    # Сохраняем результаты
    save_results(mall_data, output_file)
    
    return mall_data

if __name__ == "__main__":
    main() 