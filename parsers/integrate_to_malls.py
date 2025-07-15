"""
Скрипт для интеграции результатов парсинга в основной malls.json
"""

import json
import os
import sys

def integrate_mall_data(parsed_file, city="Москва"):
    """
    Интегрирует данные торгового центра в основной malls.json
    
    Args:
        parsed_file (str): Путь к файлу с результатами парсинга
        city (str): Город для размещения ТЦ (по умолчанию "Москва")
    """
    
    # Проверяем существование файла
    if not os.path.exists(parsed_file):
        print(f"❌ Файл {parsed_file} не найден!")
        return False
    
    # Загружаем данные парсинга
    try:
        with open(parsed_file, 'r', encoding='utf-8') as f:
            parsed_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка чтения JSON файла {parsed_file}: {e}")
        return False
    
    # Загружаем основной malls.json
    malls_file = "../malls.json"
    if not os.path.exists(malls_file):
        print(f"❌ Файл {malls_file} не найден!")
        return False
    
    try:
        with open(malls_file, 'r', encoding='utf-8') as f:
            malls_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка чтения malls.json: {e}")
        return False
    
    # Добавляем город, если его нет
    if city not in malls_data:
        malls_data[city] = {}
        print(f"✅ Добавлен город: {city}")
    
    # Интегрируем данные ТЦ
    mall_name = list(parsed_data.keys())[0]
    mall_data = parsed_data[mall_name]
    
    # Проверяем, есть ли уже такой ТЦ
    if mall_name in malls_data[city]:
        print(f"⚠️  ТЦ '{mall_name}' уже существует в malls.json")
        response = input("Заменить существующие данные? (y/N): ")
        if response.lower() != 'y':
            print("❌ Интеграция отменена")
            return False
    
    # Добавляем данные ТЦ
    malls_data[city][mall_name] = mall_data
    
    # Сохраняем обновленный malls.json
    try:
        with open(malls_file, 'w', encoding='utf-8') as f:
            json.dump(malls_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Ошибка сохранения malls.json: {e}")
        return False
    
    # Выводим статистику
    stores_count = len(mall_data.get("stores", {}))
    print(f"✅ ТЦ '{mall_name}' успешно интегрирован!")
    print(f"📊 Статистика:")
    print(f"   - Адрес: {mall_data.get('address', 'Не указан')}")
    print(f"   - Магазинов: {stores_count}")
    
    # Группируем магазины по этажам
    floors = {}
    for store_name, floor_num in mall_data.get("stores", {}).items():
        if floor_num not in floors:
            floors[floor_num] = []
        floors[floor_num].append(store_name)
    
    for floor_num in sorted(floors.keys()):
        print(f"   - {floor_num} этаж: {len(floors[floor_num])} магазинов")
    
    return True

def main():
    """
    Основная функция
    """
    
    if len(sys.argv) < 2:
        print("Использование: python integrate_to_malls.py <файл_результатов.json> [город]")
        print("Пример: python integrate_to_malls.py paveletskaya_stores.json Москва")
        return
    
    parsed_file = sys.argv[1]
    city = sys.argv[2] if len(sys.argv) > 2 else "Москва"
    
    print(f"🔄 Интеграция данных из {parsed_file} в malls.json...")
    print(f"🏙️  Город: {city}")
    
    success = integrate_mall_data(parsed_file, city)
    
    if success:
        print("🎉 Интеграция завершена успешно!")
    else:
        print("💥 Интеграция не удалась!")
        sys.exit(1)

if __name__ == "__main__":
    main() 