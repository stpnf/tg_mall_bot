#!/usr/bin/env python3
"""
Скрипт для тестирования производительности Telegram бота
Оценивает RPS (Requests Per Second) и время отклика
"""

import asyncio
import aiohttp
import time
import statistics
from typing import List, Dict
import json

# Конфигурация теста
LOGIC_API_URL = "http://localhost:8000/handle_update"
API_TOKEN = "b1e7c2f4-8a3d-4e2a-9c6b-7d2e5f1a9b3c"
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}

# Тестовые данные
TEST_PAYLOADS = [
    {
        "user_id": "test_user_1",
        "username": "test_user",
        "first_name": "Test",
        "text": "/start",
        "chat_id": 123456789
    },
    {
        "user_id": "test_user_2", 
        "username": "test_user",
        "first_name": "Test",
        "text": "Москва",
        "chat_id": 123456789
    },
    {
        "user_id": "test_user_3",
        "username": "test_user", 
        "first_name": "Test",
        "text": "Zara",
        "chat_id": 123456789
    },
    {
        "user_id": "test_user_4",
        "username": "test_user",
        "first_name": "Test", 
        "text": "🔍 Искать",
        "chat_id": 123456789
    }
]

async def make_request(session: aiohttp.ClientSession, payload: Dict) -> Dict:
    """Выполняет один запрос к API"""
    start_time = time.time()
    try:
        async with session.post(LOGIC_API_URL, json=payload, headers=HEADERS) as response:
            response_data = await response.json()
            duration = time.time() - start_time
            return {
                "success": response.status == 200,
                "duration": duration,
                "status_code": response.status,
                "response_size": len(json.dumps(response_data))
            }
    except Exception as e:
        duration = time.time() - start_time
        return {
            "success": False,
            "duration": duration,
            "error": str(e)
        }

async def concurrent_test(num_requests: int, concurrency: int) -> Dict:
    """Тест с заданным количеством запросов и уровнем конкурентности"""
    print(f"Запуск теста: {num_requests} запросов, конкурентность: {concurrency}")
    
    async with aiohttp.ClientSession() as session:
        # Создаем список задач
        tasks = []
        for i in range(num_requests):
            payload = TEST_PAYLOADS[i % len(TEST_PAYLOADS)].copy()
            payload["user_id"] = f"test_user_{i}"
            tasks.append(make_request(session, payload))
        
        # Выполняем запросы с ограничением конкурентности
        start_time = time.time()
        semaphore = asyncio.Semaphore(concurrency)
        
        async def limited_request(task):
            async with semaphore:
                return await task
        
        results = await asyncio.gather(*[limited_request(task) for task in tasks])
        total_time = time.time() - start_time
    
    # Анализируем результаты
    successful_requests = [r for r in results if r["success"]]
    failed_requests = [r for r in results if not r["success"]]
    
    if successful_requests:
        durations = [r["duration"] for r in successful_requests]
        response_sizes = [r.get("response_size", 0) for r in successful_requests]
        
        stats = {
            "total_requests": num_requests,
            "successful_requests": len(successful_requests),
            "failed_requests": len(failed_requests),
            "success_rate": len(successful_requests) / num_requests * 100,
            "total_time": total_time,
            "rps": len(successful_requests) / total_time,
            "avg_response_time": statistics.mean(durations),
            "min_response_time": min(durations),
            "max_response_time": max(durations),
            "median_response_time": statistics.median(durations),
            "avg_response_size": statistics.mean(response_sizes) if response_sizes else 0,
            "errors": [r.get("error") for r in failed_requests if "error" in r]
        }
    else:
        stats = {
            "total_requests": num_requests,
            "successful_requests": 0,
            "failed_requests": len(failed_requests),
            "success_rate": 0,
            "total_time": total_time,
            "rps": 0,
            "errors": [r.get("error") for r in failed_requests if "error" in r]
        }
    
    return stats

async def load_test():
    """Нагрузочный тест с разными уровнями конкурентности"""
    print("=== НАГРУЗОЧНЫЙ ТЕСТ TELEGRAM БОТА ===\n")
    
    test_scenarios = [
        {"requests": 10, "concurrency": 1},
        {"requests": 50, "concurrency": 5},
        {"requests": 100, "concurrency": 10},
        {"requests": 200, "concurrency": 20},
        {"requests": 500, "concurrency": 50},
        {"requests": 1000, "concurrency": 100},
    ]
    
    results = []
    
    for scenario in test_scenarios:
        print(f"Тестируем: {scenario['requests']} запросов, {scenario['concurrency']} конкурентных")
        result = await concurrent_test(scenario["requests"], scenario["concurrency"])
        results.append({**scenario, **result})
        
        print(f"  RPS: {result['rps']:.2f}")
        print(f"  Успешность: {result['success_rate']:.1f}%")
        print(f"  Среднее время ответа: {result.get('avg_response_time', 0):.3f}с")
        print(f"  Общее время: {result['total_time']:.2f}с")
        if result.get("errors"):
            print(f"  Ошибки: {len(result['errors'])}")
        print()
        
        # Пауза между тестами
        await asyncio.sleep(2)
    
    # Выводим итоговую сводку
    print("=== ИТОГОВАЯ СВОДКА ===")
    for result in results:
        print(f"RPS: {result['rps']:.2f} | "
              f"Запросы: {result['total_requests']} | "
              f"Конкурентность: {result['concurrency']} | "
              f"Успешность: {result['success_rate']:.1f}% | "
              f"Среднее время: {result.get('avg_response_time', 0):.3f}с")
    
    # Находим максимальный стабильный RPS
    stable_results = [r for r in results if r['success_rate'] >= 95]
    if stable_results:
        max_stable_rps = max(r['rps'] for r in stable_results)
        print(f"\n🎯 МАКСИМАЛЬНЫЙ СТАБИЛЬНЫЙ RPS: {max_stable_rps:.2f}")
    else:
        print("\n⚠️ Не удалось определить стабильный RPS (успешность < 95%)")

async def health_check():
    """Проверка доступности API"""
    print("Проверка доступности API...")
    async with aiohttp.ClientSession() as session:
        try:
            payload = TEST_PAYLOADS[0].copy()
            payload["user_id"] = "health_check"
            result = await make_request(session, payload)
            if result["success"]:
                print("✅ API доступен")
                return True
            else:
                print(f"❌ API недоступен: {result.get('error', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False

if __name__ == "__main__":
    async def main():
        # Проверяем доступность API
        if not await health_check():
            print("API недоступен. Убедитесь, что сервер запущен на localhost:8000")
            return
        
        print()
        await load_test()
    
    asyncio.run(main()) 