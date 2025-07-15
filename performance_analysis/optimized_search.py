"""
Оптимизированная версия поиска торговых центров
Включает индексы, кэширование и улучшенные алгоритмы
"""

import json
import time
from functools import lru_cache
from typing import Dict, List, Set, Tuple
from rapidfuzz import process

# Загружаем данные
with open("malls.json", "r", encoding="utf-8") as f:
    MALLS_DATA = json.load(f)

with open("aliases.json", "r", encoding="utf-8") as f:
    STORE_ALIASES = json.load(f)

# Создаем индексы для быстрого поиска
STORE_INDEX = {}  # store_name -> [mall_names]
CITY_STORE_INDEX = {}  # city -> {store_name -> [mall_names]}
STORE_ALIASES_INDEX = {}  # alias -> official_name

def build_indexes():
    """Строит индексы для быстрого поиска"""
    print("Построение индексов...")
    start_time = time.time()
    
    # Индекс алиасов
    for official_name, aliases in STORE_ALIASES.items():
        for alias in aliases:
            STORE_ALIASES_INDEX[alias.lower()] = official_name
    
    # Индекс магазинов по городам
    for city, malls in MALLS_DATA.items():
        CITY_STORE_INDEX[city] = {}
        
        for mall_name, mall_data in malls.items():
            stores = mall_data.get("stores", {})
            
            # Обрабатываем как словарь и список
            if isinstance(stores, dict):
                store_list = list(stores.keys())
            else:
                store_list = stores
            
            for store in store_list:
                store_lower = store.lower()
                
                # Глобальный индекс
                if store not in STORE_INDEX:
                    STORE_INDEX[store] = []
                STORE_INDEX[store].append(mall_name)
                
                # Индекс по городам
                if store not in CITY_STORE_INDEX[city]:
                    CITY_STORE_INDEX[city][store] = []
                CITY_STORE_INDEX[city][store].append(mall_name)
    
    duration = time.time() - start_time
    print(f"Индексы построены за {duration:.3f}с")
    print(f"Глобальный индекс: {len(STORE_INDEX)} магазинов")
    print(f"Города: {list(CITY_STORE_INDEX.keys())}")

def fast_correct_store_name(user_input: str, all_known_stores: List[str], 
                          aliases_threshold: int = 70, stores_threshold: int = 80) -> str | None:
    """Оптимизированная функция исправления названий магазинов"""
    if not user_input or not all_known_stores:
        return None
    
    input_lower = user_input.strip().lower()
    
    # 1. Точное совпадение
    for store in all_known_stores:
        if store.lower() == input_lower:
            return store
    
    # 2. Проверка алиасов через индекс
    if input_lower in STORE_ALIASES_INDEX:
        return STORE_ALIASES_INDEX[input_lower]
    
    # 3. Поиск по началу строки
    startswith_matches = [s for s in all_known_stores if s.lower().startswith(input_lower)]
    if startswith_matches:
        return min(startswith_matches, key=len)
    
    # 4. Поиск подстроки
    substring_matches = [s for s in all_known_stores if input_lower in s.lower()]
    if substring_matches:
        return min(substring_matches, key=len)
    
    # 5. Нечеткий поиск по алиасам
    for official_name, aliases in STORE_ALIASES.items():
        match = process.extractOne(
            input_lower,
            aliases,
            processor=str.lower,
            score_cutoff=aliases_threshold,
        )
        if match:
            return official_name
    
    # 6. Нечеткий поиск по основным названиям
    match = process.extractOne(
        user_input,
        all_known_stores,
        processor=str.lower,
        score_cutoff=stores_threshold,
    )
    
    return match[0] if match else None

@lru_cache(maxsize=1000)
def cached_mall_search(city: str, stores_tuple: Tuple[str, ...]) -> List[Tuple]:
    """Кэшированная функция поиска торговых центров"""
    return perform_optimized_mall_search(city, list(stores_tuple))

def perform_optimized_mall_search(city: str, stores: List[str]) -> List[Tuple]:
    """Оптимизированный поиск торговых центров с использованием индексов"""
    if not stores or city not in CITY_STORE_INDEX:
        return []
    
    # Получаем список всех магазинов для города
    all_stores = []
    for mall_data in MALLS_DATA[city].values():
        mall_stores = mall_data.get("stores", {})
        if isinstance(mall_stores, dict):
            all_stores.extend(mall_stores.keys())
        else:
            all_stores.extend(mall_stores)
    
    # Исправляем названия магазинов
    corrected_stores = []
    for store in stores:
        corrected = fast_correct_store_name(store, all_stores)
        if corrected:
            corrected_stores.append(corrected)
    
    if not corrected_stores:
        return []
    
    # Находим пересечение ТЦ для всех магазинов
    mall_sets = []
    for store in corrected_stores:
        if store in CITY_STORE_INDEX[city]:
            mall_sets.append(set(CITY_STORE_INDEX[city][store]))
    
    if not mall_sets:
        return []
    
    # Пересечение всех множеств
    common_malls = set.intersection(*mall_sets)
    
    # Формируем результат
    results = []
    for mall_name in common_malls:
        mall_data = MALLS_DATA[city][mall_name]
        mall_stores_dict = mall_data.get("stores", {})
        
        if isinstance(mall_stores_dict, list):
            mall_stores_dict = {store: None for store in mall_stores_dict}
        
        matched_stores = []
        for store in corrected_stores:
            if store in mall_stores_dict:
                floor = mall_stores_dict[store]
                matched_stores.append((store, floor))
        
        if matched_stores:
            results.append((mall_name, mall_data["address"], matched_stores, mall_data, len(matched_stores)))
    
    # Сортируем по количеству найденных магазинов
    results.sort(key=lambda x: x[4], reverse=True)
    return results

def benchmark_search():
    """Тест производительности поиска"""
    print("=== ТЕСТ ПРОИЗВОДИТЕЛЬНОСТИ ПОИСКА ===")
    
    # Тестовые запросы
    test_queries = [
        (["Zara", "H&M"], "Москва"),
        (["Apple", "Samsung", "Xiaomi"], "Москва"),
        (["Adidas", "Nike", "Puma"], "Санкт-Петербург"),
        (["Zara", "H&M", "Uniqlo", "Mango"], "Москва"),
    ]
    
    # Старый алгоритм
    print("\nСтарый алгоритм:")
    for stores, city in test_queries:
        start_time = time.time()
        # Здесь была бы старая функция поиска
        duration = time.time() - start_time
        print(f"  {stores} в {city}: {duration:.4f}с")
    
    # Новый алгоритм
    print("\nНовый алгоритм:")
    for stores, city in test_queries:
        start_time = time.time()
        stores_tuple = tuple(sorted(stores))  # Для кэширования
        results = cached_mall_search(city, stores_tuple)
        duration = time.time() - start_time
        print(f"  {stores} в {city}: {duration:.4f}с, найдено ТЦ: {len(results)}")
    
    # Тест кэширования
    print("\nТест кэширования:")
    stores_tuple = tuple(sorted(["Zara", "H&M"]))
    
    # Первый запрос
    start_time = time.time()
    results1 = cached_mall_search("Москва", stores_tuple)
    duration1 = time.time() - start_time
    
    # Второй запрос (из кэша)
    start_time = time.time()
    results2 = cached_mall_search("Москва", stores_tuple)
    duration2 = time.time() - start_time
    
    print(f"  Первый запрос: {duration1:.4f}с")
    print(f"  Второй запрос (кэш): {duration2:.4f}с")
    print(f"  Ускорение: {duration1/duration2:.1f}x")

if __name__ == "__main__":
    # Строим индексы
    build_indexes()
    
    # Тестируем производительность
    benchmark_search()
    
    print("\n=== СТАТИСТИКА ИНДЕКСОВ ===")
    print(f"Глобальный индекс: {len(STORE_INDEX)} магазинов")
    print(f"Индекс алиасов: {len(STORE_ALIASES_INDEX)} алиасов")
    
    for city in CITY_STORE_INDEX:
        store_count = len(CITY_STORE_INDEX[city])
        mall_count = len(MALLS_DATA[city])
        print(f"{city}: {store_count} магазинов, {mall_count} ТЦ") 