from fastapi import FastAPI, Request, Body, HTTPException
from fastapi.responses import JSONResponse
import json
import os
from datetime import datetime
from typing import Dict, Any
from rapidfuzz import process
import time
import redis.asyncio as redis
from logger import log_technical, log_user_activity
import logging
from migration_tools.user_id_map_crypto import add_mapping
from migration_tools.utils import get_user_uuid
from dotenv import load_dotenv

# Подгружаем переменные окружения (аналогично config.py)
BOT_ENV = os.getenv("BOT_ENV", "prod")
if BOT_ENV == "test":
    load_dotenv(".env.test")
else:
    load_dotenv(".env")

app = FastAPI()

USERS_FILE = os.getenv("USERS_FILE", "users.json")
MALLS_FILE = os.getenv("MALLS_FILE", "malls.json")
ALIASES_FILE = os.getenv("ALIASES_FILE", "aliases.json")
SAVED_QUERIES_FILE = os.getenv("SAVED_QUERIES_FILE", "saved_queries.json")
LOG_FILE = os.getenv("LOG_FILE", "logs/technical.json")
USER_ACTIVITY_LOG_FILE = os.getenv("USER_ACTIVITY_LOG_FILE", "logs/users_activity.json")
ERROR_LOG_FILE = os.getenv("ERROR_LOG_FILE", "logs/errors.json")

REDIS_URL = "redis://localhost:6379/0"
redis_client = redis.from_url(REDIS_URL)

# Загружаем malls.json и aliases.json при старте
with open(MALLS_FILE, "r", encoding="utf-8") as f:
    MALLS_DATA = json.load(f)
with open(ALIASES_FILE, "r", encoding="utf-8") as f:
    STORE_ALIASES = json.load(f)

WELCOME_TEXT = """
<b>Добро пожаловать в MallFinder 🛍️</b>\n\nЭтот бот поможет вам найти торговые центры, где есть нужные вам магазины.\n\n🛒 Просто:\n1. Выберите город\n2. Введите названия магазинов\n3. Получите список ТЦ с этими магазинами (с адресами и этажами)\n\n<b>Работают сокращения и синонимы названий!</b>\n\nБот не является официальным представителем указанных ТЦ и магазинов. Информация может содержать неточности или быть неактуальной.\n"""

# Список всех магазинов
ALL_STORES = set()
for city_data in MALLS_DATA.values():
    for mall in city_data.values():
        ALL_STORES.update(mall["stores"])
ALL_STORES = list(ALL_STORES)

# States
STATE_CHOOSING_CITY = "choosing_city"
STATE_ENTERING_STORE = "entering_store"
STATE_ENTERING_QUERY_NAME = "entering_query_name"
STATE_RENAMING_QUERY_NAME = "renaming_query_name"
STATE_EDITING_SAVED_QUERY = "editing_saved_query"
STATE_EDITING_SAVED_QUERY_STORES_MENU = "editing_saved_query_stores_menu"

# Меню (в виде dict для сериализации)
def city_menu():
    return {
        "keyboard": [[{"text": "Москва"}, {"text": "Санкт-Петербург"}]],
        "resize_keyboard": True,
        "is_persistent": True
    }

def after_store_menu(editing_saved_query=False):
    keyboard = [
        [{"text": "🛍️ Добавить"}, {"text": "🔍 Искать"}],
        [{"text": "🧾 Редактировать"}, {"text": "🔁 Сменить город"}],
        [{"text": "🆕 Новый поиск"}]
    ]
    if not editing_saved_query:
        keyboard.append([{"text": "📜 Список запросов"}])
    if editing_saved_query:
        keyboard.append([{"text": "⬅️ Назад"}])
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "is_persistent": True
    }

def saved_query_edit_menu():
    return {
        "keyboard": [
            [{"text": "➕ Добавить в запрос"}, {"text": "🗑 Очистить список"}],
            [{"text": "💾 Сохранить"}, {"text": "✏️ Переименовать"}],
            [{"text": "🗑 Удалить магазин"}, {"text": "⬅️ Назад"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }

def query_menu():
    return {
        "keyboard": [
            [{"text": "🛒 Редактировать магазины"}, {"text": "🔍 Искать"}],
            [{"text": "🗑 Удалить"}, {"text": "⬅️ Назад"}],
            [{"text": "🆕 Новый поиск"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": True  # Принудительно обновлять клавиатуру
    }

def reply(text, reply_markup=None, disable_web_page_preview=None):
    resp = {"text": text, "reply_markup": reply_markup}
    if disable_web_page_preview is not None:
        resp["disable_web_page_preview"] = disable_web_page_preview
    return resp

# --- Redis logging setup ---
logging.basicConfig(
    level=logging.INFO,
    filename='my_redis.log',
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logging.getLogger("redis").setLevel(logging.DEBUG)
redis_logger = logging.getLogger("myapp.redis")

# FSM helpers
async def get_state(user_id):
    state = await redis_client.get(f"user_fsm:{str(user_id)}")
    redis_logger.info(f"GET user_fsm:{str(user_id)} -> {state}")
    if state:
        return state.decode()
    return STATE_CHOOSING_CITY

async def set_state(user_id, state):
    await redis_client.set(f"user_fsm:{str(user_id)}", state)
    redis_logger.info(f"SET user_fsm:{str(user_id)} = {state}")

async def get_user_data(user_id):
    key = f"user_data:{str(user_id)}"
    data = await redis_client.get(key)
    redis_logger.info(f"GET {key} -> {data}")
    if data:
        return json.loads(data.decode('utf-8'))
    return {"city": None, "stores": []}

async def set_user_data(user_id, data):
    key = f"user_data:{str(user_id)}"
    await redis_client.set(key, json.dumps(data, ensure_ascii=False))
    redis_logger.info(f"SET {key} = {data}")

# Сохранённые запросы
# ВНИМАНИЕ: user_id должен быть UUID (а не Telegram ID)!
def load_saved_queries(user_id):
    if os.path.exists(SAVED_QUERIES_FILE):
        with open(SAVED_QUERIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    return data.get(str(user_id), [])

# ВНИМАНИЕ: user_id должен быть UUID (а не Telegram ID)!
def save_saved_queries(user_id, queries):
    if os.path.exists(SAVED_QUERIES_FILE):
        with open(SAVED_QUERIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data[str(user_id)] = queries
    with open(SAVED_QUERIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def correct_store_name(user_input, all_known_stores, aliases_threshold=70, stores_threshold=80):
    if not user_input or not all_known_stores or process is None:
        return None
    input_lower = user_input.strip().lower()
    for store in all_known_stores:
        if store.lower() == input_lower:
            return store
    for official_name, aliases in STORE_ALIASES.items():
        if input_lower in [a.lower() for a in aliases]:
            return official_name
    startswith_matches = [s for s in all_known_stores if s.lower().startswith(input_lower)]
    if startswith_matches:
        return min(startswith_matches, key=len)
    substring_matches = [s for s in all_known_stores if input_lower in s.lower()]
    if substring_matches:
        return min(substring_matches, key=len)
    for official_name, aliases in STORE_ALIASES.items():
        match = process.extractOne(
            input_lower,
            aliases,
            processor=str.lower,
            score_cutoff=aliases_threshold,
        ) if process else None
        if match:
            return official_name
    match = process.extractOne(
        user_input,
        all_known_stores,
        processor=str.lower,
        score_cutoff=stores_threshold,
    ) if process else None
    return match[0] if match else None

def log_event(user_id, event, data=None):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "event": event,
        "data": data or {}
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

API_TOKEN = os.getenv("API_TOKEN")

def check_token(request: Request):
    auth = request.headers.get("Authorization")
    if auth != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")

async def handle_start_command(user_id: str, start_time: float):
    """Обработка команды /start"""
    add_mapping(user_id)  # Добавляем пользователя в крипто-маппинг
    await set_state(user_id, STATE_CHOOSING_CITY)
    await set_user_data(user_id, {"city": None, "stores": []})
    response = reply(WELCOME_TEXT, city_menu(), disable_web_page_preview=True)
    duration = time.time() - start_time
    log_technical(get_user_uuid(user_id), "bot_response", details={"text": WELCOME_TEXT, "duration": duration})
    log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
    return JSONResponse(response)

async def handle_city_selection(user_id: str, text: str, start_time: float):
    """Обработка выбора города"""
    if text not in MALLS_DATA:
        response = reply("Пока доступны только Москва и Санкт-Петербург", city_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Пока доступны только Москва и Санкт-Петербург", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    await set_user_data(user_id, {"city": text, "stores": [], "current_query_index": None})
    await set_state(user_id, STATE_ENTERING_STORE)
    log_user_activity(get_user_uuid(user_id), "city_selected", {"city": text})
    response_text = f"Вы выбрали город: <b>{text}</b>.\n\nТеперь вы можете:\n🛍️ Добавить — ввести название магазина\n🔍 Искать — найти ТЦ с нужными магазинами\n🧾 Редактировать — посмотреть или удалить магазины\n\nВведите название магазина и нажмите ввод"
    response = reply(response_text, after_store_menu(), disable_web_page_preview=True)
    duration = time.time() - start_time
    log_technical(get_user_uuid(user_id), "bot_response", details={"text": response_text, "duration": duration})
    log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
    return JSONResponse(response)

async def handle_store_editing(user_id: str, start_time: float):
    """Обработка редактирования списка магазинов"""
    log_user_activity(get_user_uuid(user_id), "menu_action", {"action": "edit_stores_list"})
    user_data = await get_user_data(user_id)
    # Сброс current_query_index, если он был выставлен
    if user_data.get("current_query_index") is not None:
        user_data["current_query_index"] = None
        await set_user_data(user_id, user_data)
    stores = user_data["stores"]
    if not stores:
        response = reply("Список пуст (изменения не сохранятся в запросе)", after_store_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Список пуст (изменения не сохранятся в запросе)", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    response_text = "<b>Ваш список магазинов (изменения не сохранятся в запросе):</b>\n"
    for i, store in enumerate(stores, 1):
        response_text += f"{i}. {store}\n"
    response_text += "\nЧтобы удалить магазин — отправь его номер"
    response = reply(response_text, after_store_menu(), disable_web_page_preview=True)
    duration = time.time() - start_time
    log_technical(get_user_uuid(user_id), "bot_response", details={"text": response_text, "duration": duration})
    log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
    return JSONResponse(response)

async def handle_city_change(user_id: str, start_time: float):
    """Обработка смены города"""
    log_user_activity(get_user_uuid(user_id), "menu_action", {"action": "change_city"})
    await set_state(user_id, STATE_CHOOSING_CITY)
    await set_user_data(user_id, {"city": None, "stores": [], "current_query_index": None})
    response = reply("Выберите город:", city_menu(), disable_web_page_preview=True)
    duration = time.time() - start_time
    log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Выберите город:", "duration": duration})
    log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
    return JSONResponse(response)

async def handle_mall_search(user_id: str, start_time: float):
    """Обработка поиска торговых центров"""
    log_user_activity(get_user_uuid(user_id), "menu_action", {"action": "search_malls"})
    user_data = await get_user_data(user_id)
    city = user_data.get("city")
    queries = user_data.get("stores", [])
    
    if not city:
        response = reply("Сначала выберите город через /start", after_store_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Сначала выберите город через /start", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    if not queries:
        response = reply("Сначала добавьте магазины для поиска", after_store_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Сначала добавьте магазины для поиска", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    log_user_activity(get_user_uuid(user_id), "store_search", {"city": city, "stores": queries})
    results = []
    for mall_name, mall_data in MALLS_DATA[city].items():
        mall_stores_dict = mall_data.get("stores", {})
        if isinstance(mall_stores_dict, list):
            mall_stores_dict = {store: None for store in mall_stores_dict}
        mall_stores_lower = {
            store.lower(): (store, floor)
            for store, floor in mall_stores_dict.items()
        }
        matched_stores = []
        found_store_queries = set()
        for store_query in queries:
            corrected_query = correct_store_name(store_query, ALL_STORES) or store_query
            for store_lower, (original_store, floor) in mall_stores_lower.items():
                if corrected_query.lower() == store_lower:
                    matched_stores.append((original_store, floor))
                    found_store_queries.add(store_query.lower())
                    break
        if matched_stores:
            results.append((mall_name, mall_data["address"], matched_stores, mall_data, len(found_store_queries)))
    
    if not results:
        log_user_activity(get_user_uuid(user_id), "search_result", {"result": "no_matches", "city": city, "stores": queries})
        response = reply("Магазины не найдены 😔", after_store_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Магазины не найдены 😔", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    results.sort(key=lambda x: x[4], reverse=True)
    total_user_selected = len(queries)
    full_response = ""
    for mall, address, matched_stores, mall_data, matched_count in results:
        yandex_link = mall_data.get("map_link") or f"https://yandex.ru/maps/?text={address.replace(' ', '+')}"
        matched_stores = [tuple(item) for item in matched_stores]
        matched_stores = list({(name, floor) for name, floor in matched_stores})
        matched_stores.sort(key=lambda x: (x[1] is None, x[1]))
        text_result = f"🏬 <b>{mall}</b> — {matched_count} / {total_user_selected} магазинов\n"
        text_result += f"<a href='{yandex_link}'>{address}</a>\n\n"
        for name, floor in matched_stores:
            if floor is None:
                floor_info = " — нет данных"
            else:
                floor_info = f" — {floor} этаж"
            text_result += f"• {name}{floor_info}\n"
        full_response += text_result + "\n"
    
    log_user_activity(get_user_uuid(user_id), "search_result", {"result": "found", "city": city, "stores": queries, "malls_found": len(results)})
    response = reply(full_response.strip(), after_store_menu(), disable_web_page_preview=True)
    duration = time.time() - start_time
    log_technical(get_user_uuid(user_id), "bot_response", details={"text": full_response.strip(), "duration": duration})
    log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
    return JSONResponse(response)

async def handle_clear_stores_list(user_id: str, start_time: float):
    """Обработка очистки списка магазинов"""
    log_user_activity(get_user_uuid(user_id), "menu_action", {"action": "clear_stores_list"})
    user_data = await get_user_data(user_id)
    user_data["stores"] = []
    user_data["current_query_index"] = None # сброс индекса
    await set_user_data(user_id, user_data)
    log_user_activity(get_user_uuid(user_id), "query_stores_updated", {"stores": []})
    response = reply("Список магазинов очищен", after_store_menu(), disable_web_page_preview=True)
    duration = time.time() - start_time
    log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Список магазинов очищен", "duration": duration})
    log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
    return JSONResponse(response)

async def handle_show_saved_queries(user_id: str, start_time: float):
    """Обработка показа сохраненных запросов"""
    log_user_activity(get_user_uuid(user_id), "menu_action", {"action": "show_saved_queries"})
    queries = load_saved_queries(get_user_uuid(user_id))
    user_data = await get_user_data(user_id)
    user_data["current_query_index"] = None # сброс индекса
    await set_user_data(user_id, user_data)
    if not queries:
        log_user_activity(get_user_uuid(user_id), "saved_queries_action", {"action": "view", "result": "empty"})
        response = reply("У вас нет сохранённых запросов", after_store_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "У вас нет сохранённых запросов", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    log_user_activity(get_user_uuid(user_id), "saved_queries_action", {"action": "view", "result": "found", "count": len(queries)})
    lines = []
    buttons = []
    for i, q in enumerate(queries):
        stores_str = ", ".join(q["stores"])
        lines.append(f"{i + 1}. <b>{q['name']}</b>\n{stores_str}")
        buttons.append([{"text": q["name"], "callback_data": f"load_query::{i}"}])
    text_out = "\n\n".join(lines)
    keyboard = {"inline_keyboard": buttons}
    response = reply(text_out + "\n\nВыберите список для загрузки:", keyboard, disable_web_page_preview=True)
    duration = time.time() - start_time
    log_technical(get_user_uuid(user_id), "bot_response", details={"text": text_out + "\n\nВыберите список для загрузки:", "duration": duration})
    log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
    return JSONResponse(response)

async def handle_add_store_prompt(user_id: str, start_time: float):
    """Обработка запроса на добавление магазина"""
    log_user_activity(get_user_uuid(user_id), "menu_action", {"action": "add_store_prompt"})
    response = reply("Введите название магазина:", after_store_menu(), disable_web_page_preview=True)
    duration = time.time() - start_time
    log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Введите название магазина:", "duration": duration})
    log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
    return JSONResponse(response)

async def handle_new_search(user_id: str, start_time: float):
    """Обработка начала нового поиска"""
    log_user_activity(get_user_uuid(user_id), "menu_action", {"action": "new_search"})
    user_data = await get_user_data(user_id)
    user_data["stores"] = []
    user_data["current_query_index"] = None # сброс индекса
    await set_user_data(user_id, user_data)
    log_user_activity(get_user_uuid(user_id), "query_stores_updated", {"stores": []})
    response = reply(
        "✅ Начат новый пустой поиск.\n\nТеперь вы можете:\n🛍️ Добавить — ввести название магазина\n🔍 Искать — найти ТЦ с нужными магазинами\n🧾 Редактировать — посмотреть или удалить магазины\n\nВведите название магазина и нажмите ввод",
        after_store_menu(),
        disable_web_page_preview=True
    )
    duration = time.time() - start_time
    log_technical(get_user_uuid(user_id), "bot_response", details={"text": "✅ Начат новый пустой поиск. Теперь вы можете: ...", "duration": duration})
    log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
    return JSONResponse(response)

async def handle_store_number_input(user_id: str, text: str, start_time: float):
    """Обработка ввода номера магазина"""
    user_data = await get_user_data(user_id)
    stores = user_data["stores"]
    index = int(text) - 1
    
    # Сначала проверяем удаление магазина из текущего списка
    if 0 <= index < len(stores):
        removed = stores.pop(index)
        user_data["stores"] = stores
        await set_user_data(user_id, user_data)
        log_user_activity(get_user_uuid(user_id), "store_removed", {"store": removed, "method": "by_number", "remaining_count": len(stores)})
        response = reply(f"Магазин <b>{removed}</b> удалён из списка", after_store_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": f"Магазин <b>{removed}</b> удалён из списка", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    # Если номер не подходит для удаления магазина, проверяем загрузку сохраненного запроса
    queries = load_saved_queries(get_user_uuid(user_id))
    if 0 <= index < len(queries):
        log_user_activity(get_user_uuid(user_id), "saved_queries_action", {"action": "load_by_number", "query_index": index, "query_name": queries[index]["name"]})
        user_data = await get_user_data(user_id)
        user_data["stores"] = list(queries[index]["stores"])
        user_data["current_query_index"] = index
        await set_user_data(user_id, user_data)
        await set_state(user_id, STATE_EDITING_SAVED_QUERY)
        response_text = f"Загружен список <b>{queries[index]['name']}</b>:\n\n"
        for i, store in enumerate(queries[index]["stores"], 1):
            response_text += f"{i}. {store}\n"
        response = reply(response_text, query_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": response_text, "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    # Если номер не подходит ни для удаления, ни для загрузки
    log_user_activity(get_user_uuid(user_id), "input_error", {"error": "invalid_store_number", "input": text, "max_valid": len(stores)})
    response = reply("❌ Неверный номер", after_store_menu(), disable_web_page_preview=True)
    duration = time.time() - start_time
    log_technical(get_user_uuid(user_id), "bot_response", details={"text": "❌ Неверный номер", "duration": duration})
    log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
    return JSONResponse(response)

async def handle_store_name_input(user_id: str, text: str, start_time: float):
    """Обработка ввода названия магазина"""
    user_data = await get_user_data(user_id)
    state = await get_state(user_id)
    current_query_index = user_data.get("current_query_index")
    # Не сбрасываем current_query_index, если редактируем сохранённый запрос
    if state == STATE_ENTERING_STORE and current_query_index is not None:
        # Оставляем current_query_index, чтобы меню не менялось
        pass
    corrected = correct_store_name(text, ALL_STORES)
    if not corrected:
        log_user_activity(get_user_uuid(user_id), "store_not_found", {"input": text, "suggestions": []})
        menu = saved_query_edit_menu() if current_query_index is not None else after_store_menu()
        response = reply(f"❌ Магазин <b>{text}</b> не найден. Попробуйте снова.", menu, disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": f"❌ Магазин <b>{text}</b> не найден. Попробуйте снова.", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    user_data = await get_user_data(user_id)
    if corrected.lower() in [s.lower() for s in user_data["stores"]]:
        log_user_activity(get_user_uuid(user_id), "store_already_exists", {"store": corrected, "input": text})
        menu = saved_query_edit_menu() if current_query_index is not None else after_store_menu()
        response = reply(f"🔁 Магазин <b>{corrected}</b> уже есть в списке", menu, disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": f"🔁 Магазин <b>{corrected}</b> уже есть в списке", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    user_data["stores"] = user_data["stores"] + [corrected]
    await set_user_data(user_id, user_data)
    # Если редактируем сохранённый запрос, обновляем его
    if current_query_index is not None:
        queries = load_saved_queries(get_user_uuid(user_id))
        if 0 <= current_query_index < len(queries):
            queries[current_query_index]["stores"] = list(user_data["stores"])
            save_saved_queries(get_user_uuid(user_id), queries)
    log_user_activity(get_user_uuid(user_id), "store_added", {"store": corrected, "input": text, "was_corrected": text != corrected})
    response_text = f"<b>Магазин добавлен:</b> {corrected}\n\n"
    response_text += "<b>Текущий список:</b>\n"
    user_data = await get_user_data(user_id)
    for i, store in enumerate(user_data["stores"], 1):
        response_text += f"{i}. {store}\n"
    if current_query_index is not None:
        menu = saved_query_edit_menu()
        await set_state(user_id, STATE_EDITING_SAVED_QUERY_STORES_MENU)
        log_technical(get_user_uuid(user_id), "menu_selection", details={"menu": "saved_query_edit_menu", "current_query_index": current_query_index})
        response = reply(response_text, menu, disable_web_page_preview=True)
    else:
        # Инлайн-кнопки: "Это не тот магазин" и "Сохранить запрос"
        # Сохраняем исходный пользовательский ввод в user_data['store_choices']
        user_data = await get_user_data(user_id)
        store_choices = user_data.get("store_choices", [])
        store_choices.append(text)
        user_data["store_choices"] = store_choices
        await set_user_data(user_id, user_data)
        user_input_index = len(store_choices) - 1
        corrected_index = user_input_index  # по умолчанию, если только что добавили
        log_technical(get_user_uuid(user_id), "debug", details={"message": f"Added store '{corrected}', original input '{text}', store_choices: {store_choices}"})
        keyboard = {"inline_keyboard": [
            [{"text": "❌ Это не тот магазин", "callback_data": f"wrong_store::0::{corrected_index}"}],
            [{"text": "💾 Сохранить запрос", "callback_data": "save_query"}]
        ]}
        menu = after_store_menu()
        log_technical(get_user_uuid(user_id), "menu_selection", details={"menu": "after_store_menu", "current_query_index": None})
        response = reply(response_text, keyboard, disable_web_page_preview=True)
    duration = time.time() - start_time
    log_technical(get_user_uuid(user_id), "bot_response", details={"text": response_text, "duration": duration})
    log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
    return JSONResponse(response)

async def handle_saved_query_actions(user_id: str, text: str, start_time: float):
    """Обработка действий с сохраненными запросами"""
    # Добавлено: обработка кнопки '📜 Список запросов' из любого режима
    if text == "📜 Список запросов":
        return await handle_show_saved_queries(user_id, start_time)
    user_data = await get_user_data(user_id)
    idx = user_data.get("current_query_index")
    queries = load_saved_queries(get_user_uuid(user_id))
    
    if text == "✏️ Переименовать":
        log_user_activity(get_user_uuid(user_id), "saved_query_action", {"action": "rename_prompt", "query_index": idx})
        await set_state(user_id, STATE_RENAMING_QUERY_NAME)
        response = reply("Введите новое название:", query_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Введите новое название:", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    if text == "🛒 Редактировать магазины":
        log_user_activity(get_user_uuid(user_id), "saved_query_action", {"action": "edit_stores", "query_index": idx})
        if idx is not None and 0 <= idx < len(queries):
            user_data["stores"] = list(queries[idx]["stores"])
            user_data["current_query_index"] = idx
            await set_user_data(user_id, user_data)
        user_data = await get_user_data(user_id)
        stores = user_data["stores"]
        await set_state(user_id, STATE_ENTERING_STORE)
        response = reply("Выберите действие", saved_query_edit_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Выберите действие", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    if text == "🆕 Новый поиск":
        log_user_activity(get_user_uuid(user_id), "saved_query_action", {"action": "new_search_from_saved", "query_index": idx})
        user_data = await get_user_data(user_id)
        user_data["stores"] = []
        user_data["current_query_index"] = None # сброс индекса
        await set_user_data(user_id, user_data)
        await set_state(user_id, STATE_ENTERING_STORE)
        response = reply(
            "✅ Начат новый пустой поиск.\n\nТеперь вы можете:\n🛍️ Добавить — ввести название магазина\n🔍 Искать — найти ТЦ с нужными магазинами\n🧾 Редактировать — посмотреть или удалить магазины\n\nВведите название магазина и нажмите ввод",
            after_store_menu(),
            disable_web_page_preview=True
        )
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "✅ Начат новый пустой поиск. Теперь вы можете: ...", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    if text == "🔍 Искать":
        log_user_activity(get_user_uuid(user_id), "saved_query_action", {"action": "search_from_saved", "query_index": idx})
        await set_state(user_id, STATE_ENTERING_STORE)
        return await handle_mall_search(user_id, start_time)
    
    if text == "🗑 Удалить":
        log_user_activity(get_user_uuid(user_id), "saved_query_action", {"action": "delete", "query_index": idx})
        if idx is not None and 0 <= idx < len(queries):
            queries.pop(idx)
            save_saved_queries(get_user_uuid(user_id), queries)
            log_user_activity(get_user_uuid(user_id), "query_deleted", {"query_index": idx})
            await set_state(user_id, STATE_ENTERING_STORE)
            user_data = await get_user_data(user_id)
            user_data["current_query_index"] = None  # сброс индекса
            await set_user_data(user_id, user_data)
            response = reply("Запрос удалён.", after_store_menu(), disable_web_page_preview=True)
            duration = time.time() - start_time
            log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Запрос удалён.", "duration": duration})
            log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
            return JSONResponse(response)
        else:
            log_user_activity(get_user_uuid(user_id), "error", {"error": "query_not_found", "query_index": idx})
            user_data = await get_user_data(user_id)
            user_data["current_query_index"] = None  # сброс индекса
            await set_user_data(user_id, user_data)
            response = reply("Не удалось удалить запрос. Возможно, он уже был удалён или не существует.", after_store_menu(), disable_web_page_preview=True)
            duration = time.time() - start_time
            log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Не удалось удалить запрос. Возможно, он уже был удалён или не существует.", "duration": duration})
            log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
            return JSONResponse(response)
    
    if text == "⬅️ Назад":
        log_user_activity(get_user_uuid(user_id), "navigation", {"action": "back_to_main_menu"})
        await set_state(user_id, STATE_ENTERING_STORE)
        user_data = await get_user_data(user_id)
        user_data["current_query_index"] = None  # сброс индекса
        await set_user_data(user_id, user_data)
        response = reply("Выберите действие:", after_store_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Выберите действие:", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    log_user_activity(get_user_uuid(user_id), "input_error", {"error": "unknown_command_in_saved_query", "input": text})
    response = reply("Выберите действие:", query_menu(), disable_web_page_preview=True)
    duration = time.time() - start_time
    log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Выберите действие:", "duration": duration})
    log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
    return JSONResponse(response)

async def handle_query_renaming(user_id: str, text: str, start_time: float):
    """Обработка переименования запроса"""
    user_data = await get_user_data(user_id)
    idx = user_data.get("current_query_index")
    queries = load_saved_queries(get_user_uuid(user_id))
    new_name = text
    
    if idx is None or not (0 <= idx < len(queries)):
        log_user_activity(get_user_uuid(user_id), "error", {"error": "query_not_found_for_rename", "query_index": idx})
        await set_state(user_id, STATE_ENTERING_STORE)
        response = reply("🔎 Не удалось найти этот запрос. Возможно, он был удалён. Пожалуйста, выберите другой из списка или создайте новый.", after_store_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "🔎 Не удалось найти этот запрос. Возможно, он был удалён. Пожалуйста, выберите другой из списка или создайте новый.", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    queries[idx]["name"] = new_name
    save_saved_queries(get_user_uuid(user_id), queries)
    log_user_activity(get_user_uuid(user_id), "query_renamed", {"query_index": idx, "new_name": new_name})
    await set_state(user_id, STATE_EDITING_SAVED_QUERY_STORES_MENU)
    response = reply("✅ Название обновлено", saved_query_edit_menu(), disable_web_page_preview=True)
    duration = time.time() - start_time
    log_technical(get_user_uuid(user_id), "bot_response", details={"text": "✅ Название обновлено", "duration": duration})
    log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
    return JSONResponse(response)

async def handle_saved_query_stores_editing(user_id: str, text: str, start_time: float):
    """Обработка редактирования магазинов в сохраненном запросе"""
    user_data = await get_user_data(user_id)
    idx = user_data.get("current_query_index")
    queries = load_saved_queries(get_user_uuid(user_id))
    
    if idx is None or not (0 <= idx < len(queries)):
        log_user_activity(get_user_uuid(user_id), "error", {"error": "query_not_found_for_edit", "query_index": idx})
        await set_state(user_id, STATE_EDITING_SAVED_QUERY)
        response = reply("🔎 Не удалось найти этот запрос. Возможно, он был удалён. Пожалуйста, выберите другой из списка или создайте новый.", query_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": " Не удалось найти этот запрос. Возможно, он был удалён. Пожалуйста, выберите другой из списка или создайте новый.", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    if text == "⬅️ Назад":
        log_user_activity(get_user_uuid(user_id), "navigation", {"action": "back_to_saved_query_menu"})
        await set_state(user_id, STATE_EDITING_SAVED_QUERY)
        response = reply("Выберите действие:", query_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Выберите действие:", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    if text == "🗑 Очистить список":
        log_user_activity(get_user_uuid(user_id), "saved_query_action", {"action": "clear_stores", "query_index": idx})
        user_data = await get_user_data(user_id)
        user_data["stores"] = []
        await set_user_data(user_id, user_data)
        queries[idx]["stores"] = []
        save_saved_queries(get_user_uuid(user_id), queries)
        log_user_activity(get_user_uuid(user_id), "query_stores_updated", {"stores": []})
        response = reply("✅ Изменения сохранены", saved_query_edit_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "✅ Изменения сохранены", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    if text == "💾 Сохранить":
        log_user_activity(get_user_uuid(user_id), "saved_query_action", {"action": "save_changes", "query_index": idx})
        user_data = await get_user_data(user_id)
        queries[idx]["stores"] = list(user_data["stores"])
        save_saved_queries(get_user_uuid(user_id), queries)
        log_user_activity(get_user_uuid(user_id), "query_saved", {"query_index": idx, "stores": user_data["stores"]})
        response = reply("✅ Изменения сохранены", saved_query_edit_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "✅ Изменения сохранены", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    if text == "✏️ Переименовать":
        log_user_activity(get_user_uuid(user_id), "saved_query_action", {"action": "rename_prompt_from_edit", "query_index": idx})
        await set_state(user_id, STATE_RENAMING_QUERY_NAME)
        response = reply("Введите новое название:", saved_query_edit_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Введите новое название:", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    if text == "➕ Добавить в запрос":
        log_user_activity(get_user_uuid(user_id), "saved_query_action", {"action": "add_store_prompt", "query_index": idx})
        await set_state(user_id, STATE_ENTERING_STORE)
        response = reply("Введите название магазина, который хотите добавить:", saved_query_edit_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Введите название магазина, который хотите добавить:", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    if text == "🗑 Удалить магазин":
        log_user_activity(get_user_uuid(user_id), "saved_query_action", {"action": "remove_store_prompt", "query_index": idx})
        user_data = await get_user_data(user_id)
        stores = user_data["stores"]
        if not stores:
            response = reply("Список пуст", saved_query_edit_menu(), disable_web_page_preview=True)
            duration = time.time() - start_time
            log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Список пуст", "duration": duration})
            log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
            return JSONResponse(response)
        response_text = "<b>Ваш список магазинов:</b>\n"
        for i, store in enumerate(stores, 1):
            response_text += f"{i}. {store}\n"
        response_text += "\nВведите номер магазина, который хотите удалить."
        response = reply(response_text, saved_query_edit_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": response_text, "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    if text.isdigit():
        index = int(text) - 1
        user_data = await get_user_data(user_id)
        stores = user_data["stores"]
        if 0 <= index < len(stores):
            removed = stores.pop(index)
            queries[idx]["stores"] = list(stores)
            save_saved_queries(get_user_uuid(user_id), queries)
            user_data["stores"] = stores
            await set_user_data(user_id, user_data)
            log_user_activity(get_user_uuid(user_id), "query_stores_updated", {"removed_store": removed, "stores": stores, "method": "by_number"})
            await set_state(user_id, STATE_EDITING_SAVED_QUERY_STORES_MENU)
            response = reply(f"Магазин <b>{removed}</b> удалён из списка", saved_query_edit_menu(), disable_web_page_preview=True)
            duration = time.time() - start_time
            log_technical(get_user_uuid(user_id), "bot_response", details={"text": f"Магазин <b>{removed}</b> удалён из списка", "duration": duration})
            log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
            return JSONResponse(response)
        else:
            log_user_activity(get_user_uuid(user_id), "input_error", {"error": "invalid_store_number_in_saved", "input": text, "max_valid": len(stores)})
            response = reply("Похоже, вы ввели неверный номер магазина. Проверьте список и попробуйте снова.", saved_query_edit_menu(), disable_web_page_preview=True)
            duration = time.time() - start_time
            log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Похоже, вы ввели неверный номер магазина. Проверьте список и попробуйте снова.", "duration": duration})
            log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
            return JSONResponse(response)
    
    # Добавление магазина в сохраненный запрос
    corrected = correct_store_name(text, ALL_STORES)
    if not corrected:
        log_user_activity(get_user_uuid(user_id), "store_not_found_in_saved", {"input": text, "query_index": idx})
        response = reply(f"❌ Магазин <b>{text}</b> не найден. Попробуйте снова.", saved_query_edit_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": f"❌ Магазин <b>{text}</b> не найден. Попробуйте снова.", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    user_data = await get_user_data(user_id)
    if corrected.lower() in [s.lower() for s in user_data["stores"]]:
        log_user_activity(get_user_uuid(user_id), "store_already_exists_in_saved", {"store": corrected, "input": text, "query_index": idx})
        response = reply(f"🔁 Магазин <b>{corrected}</b> уже есть в списке.", saved_query_edit_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": f"🔁 Магазин <b>{corrected}</b> уже есть в списке.", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
    
    user_data["stores"] = user_data["stores"] + [corrected]
    await set_user_data(user_id, user_data)
    user_data = await get_user_data(user_id)
    queries[idx]["stores"] = list(user_data["stores"])
    save_saved_queries(get_user_uuid(user_id), queries)
    log_user_activity(get_user_uuid(user_id), "query_stores_updated", {"added_store": corrected, "stores": user_data["stores"], "input": text, "was_corrected": text != corrected})
    response_text = f"<b>Магазин добавлен:</b> {corrected}\n\n"
    response_text += "<b>Текущий список:</b>\n"
    for i, store in enumerate(user_data["stores"], 1):
        response_text += f"{i}. {store}\n"
    response = reply(response_text, saved_query_edit_menu(), disable_web_page_preview=True)
    duration = time.time() - start_time
    log_technical(get_user_uuid(user_id), "bot_response", details={"text": response_text, "duration": duration})
    log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
    return JSONResponse(response)

@app.post("/handle_update")
async def handle_update(request: Request):
    start_time = time.time()
    
    # Логируем входящий HTTP запрос
    log_technical(None, "http_request", details={
        "method": "POST",
        "path": "/handle_update",
        "timestamp": datetime.now().isoformat()
    })
    
    try:
        check_token(request)
        data = await request.json()
        user_id = data.get("user_id")
        text = (data.get("text") or "").strip()
        
        # Обновляем лог с информацией о пользователе
        log_technical(get_user_uuid(user_id), "http_request", details={
            "method": "POST",
            "path": "/handle_update",
            "user_id": user_id,
            "text": text[:100] if text else None,  # Ограничиваем длину текста
            "timestamp": datetime.now().isoformat()
        })
        
        if not user_id:
            response = reply("Произошла ошибка. Пожалуйста, попробуйте ещё раз или начните сначала.", disable_web_page_preview=True)
            duration = time.time() - start_time
            log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Произошла ошибка. Пожалуйста, попробуйте ещё раз или начните сначала.", "duration": duration})
            log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
            return JSONResponse(response)
        
        user_data = await get_user_data(user_id)
        state = await get_state(user_id)

        # /start
        if text == "/start":
            return await handle_start_command(user_id, start_time)

        # FSM: выбор города
        if state == STATE_CHOOSING_CITY:
            return await handle_city_selection(user_id, text, start_time)

        # FSM: ввод магазинов
        if state == STATE_ENTERING_STORE:
            # Обычные кнопки для обычного режима (обрабатываются всегда, даже если есть current_query_index)
            if text == "🧾 Редактировать":
                return await handle_store_editing(user_id, start_time)
            if text == "🔁 Сменить город":
                return await handle_city_change(user_id, start_time)
            if text == "🔍 Искать":
                return await handle_mall_search(user_id, start_time)
            if text == "🗑 Очистить список":
                return await handle_clear_stores_list(user_id, start_time)
            if text == "📜 Список запросов":
                return await handle_show_saved_queries(user_id, start_time)
            if text == "🛍️ Добавить":
                return await handle_add_store_prompt(user_id, start_time)
            if text == "🆕 Новый поиск":
                return await handle_new_search(user_id, start_time)
            user_data = await get_user_data(user_id)
            if user_data.get("current_query_index") is not None:
                # Обрабатываем все действия (включая ввод номера) через handle_saved_query_stores_editing
                return await handle_saved_query_stores_editing(user_id, text, start_time)
            if text.isdigit():
                return await handle_store_number_input(user_id, text, start_time)
            # Добавление магазина
            return await handle_store_name_input(user_id, text, start_time)

        # FSM: работа с сохранённым запросом
        if state == STATE_EDITING_SAVED_QUERY:
            return await handle_saved_query_actions(user_id, text, start_time)

        # FSM: переименование запроса
        if state == STATE_RENAMING_QUERY_NAME:
            return await handle_query_renaming(user_id, text, start_time)

        # FSM: редактирование магазинов в сохранённом запросе
        if state == STATE_EDITING_SAVED_QUERY_STORES_MENU:
            return await handle_saved_query_stores_editing(user_id, text, start_time)

        # FSM: ввод названия нового запроса
        if state == STATE_ENTERING_QUERY_NAME:
            user_data = await get_user_data(user_id)
            query_name = text.strip()
            if not query_name:
                response = reply("Название запроса не может быть пустым. Пожалуйста, введите название:", disable_web_page_preview=True)
                duration = time.time() - start_time
                log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Название запроса не может быть пустым. Пожалуйста, введите название:", "duration": duration})
                log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
                return JSONResponse(response)
            queries = load_saved_queries(get_user_uuid(user_id))
            # Генерируем уникальный id
            if queries:
                max_id = max(q.get("id", 0) for q in queries)
                new_id = max_id + 1
            else:
                new_id = 1
            new_query = {"id": new_id, "name": query_name, "stores": list(user_data.get("stores", [])), "city": user_data.get("city")}
            queries.append(new_query)
            save_saved_queries(get_user_uuid(user_id), queries)
            user_data["current_query_index"] = None
            await set_user_data(user_id, user_data)
            await set_state(user_id, STATE_ENTERING_STORE)
            response = reply(f"✅ Запрос <b>{query_name}</b> сохранён!", after_store_menu(), disable_web_page_preview=True)
            duration = time.time() - start_time
            log_technical(get_user_uuid(user_id), "bot_response", details={"text": f"✅ Запрос <b>{query_name}</b> сохранён!", "duration": duration})
            log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
            return JSONResponse(response)

        # fallback
        log_user_activity(get_user_uuid(user_id), "navigation", {"action": "fallback_to_start"})
        response = reply("Не удалось распознать действие. Пожалуйста, начните сначала с команды /start", city_menu(), disable_web_page_preview=True)
        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Не удалось распознать действие. Пожалуйста, начните сначала с команды /start", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
        
    except HTTPException as e:
        duration = time.time() - start_time
        log_technical(None, "http_response", details={"status_code": e.status_code, "status": e.detail, "duration": duration})
        raise
    except Exception as e:
        duration = time.time() - start_time
        log_technical(None, "http_response", details={"status_code": 500, "status": "Internal Server Error", "error": str(e), "duration": duration})
        raise

@app.post("/handle_callback")
async def handle_callback(request: Request):
    start_time = time.time()
    
    # Логируем входящий HTTP запрос
    log_technical(None, "http_request", details={
        "method": "POST", 
        "path": "/handle_callback",
        "timestamp": datetime.now().isoformat()
    })
    
    try:
        check_token(request)
        data = await request.json()
        user_id = data.get("user_id")
        callback_data = data.get("callback_data")
        message_id = data.get("message_id")
        chat_id = data.get("chat_id")
        
        # Обновляем лог с информацией о пользователе
        log_technical(get_user_uuid(user_id), "http_request", details={
            "method": "POST", 
            "path": "/handle_callback",
            "user_id": user_id,
            "callback_data": callback_data,
            "message_id": message_id,
            "chat_id": chat_id,
            "timestamp": datetime.now().isoformat()
        })
        
        if not user_id or not callback_data:
            response = reply("Не удалось выполнить действие. Пожалуйста, попробуйте ещё раз или перезапустите бота.", disable_web_page_preview=True)
            duration = time.time() - start_time
            log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Не удалось выполнить действие. Пожалуйста, попробуйте ещё раз или перезапустите бота.", "duration": duration})
            log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
            return JSONResponse(response)
        state = await get_state(user_id)
        log_technical(get_user_uuid(user_id), "callback_query", details={"callback_data": callback_data, "state": state})

        # wrong_store::<user_input_index>::<corrected_index>
        if callback_data.startswith("wrong_store::"):
            log_user_activity(get_user_uuid(user_id), "callback_action", {"action": "wrong_store_correction"})
            log_technical(get_user_uuid(user_id), "debug", details={"message": f"Processing wrong_store callback: {callback_data}"})
            parts = callback_data.split("::")
            if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
                response = reply("Не удалось выполнить действие. Пожалуйста, попробуйте ещё раз или начните сначала.", disable_web_page_preview=True)
                duration = time.time() - start_time
                log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Не удалось выполнить действие. Пожалуйста, попробуйте ещё раз или начните сначала.", "duration": duration})
                log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
                return JSONResponse(response)
            user_input_index = int(parts[1])
            corrected_index = int(parts[2])
            log_technical(get_user_uuid(user_id), "debug", details={"message": f"Parsed indices: user_input_index={user_input_index}, corrected_index={corrected_index}"})
            user_data = await get_user_data(user_id)
            store_choices = user_data.get("store_choices", [])
            log_technical(get_user_uuid(user_id), "debug", details={"message": f"Before removal - stores: {user_data.get('stores', [])}, store_choices: {store_choices}"})
            
            # Удаляем последний добавленный магазин из списка
            stores = user_data.get("stores", [])
            if stores:
                last_added_store = stores[-1]
                user_data["stores"] = stores[:-1]  # Удаляем последний элемент
                await set_user_data(user_id, user_data)
                log_user_activity(get_user_uuid(user_id), "store_removed", {"store": last_added_store, "method": "wrong_store_callback"})
                log_technical(get_user_uuid(user_id), "debug", details={"message": f"Removed store '{last_added_store}', remaining stores: {user_data.get('stores', [])}"})
                log_technical(get_user_uuid(user_id), "debug", details={"message": f"After removal - stores: {user_data.get('stores', [])}, store_choices: {user_data.get('store_choices', [])}"})
            else:
                last_added_store = None
                log_technical(get_user_uuid(user_id), "debug", details={"message": "No stores to remove"})
            
            # Получаем исходный пользовательский ввод
            log_technical(get_user_uuid(user_id), "debug", details={"message": f"store_choices: {store_choices}, user_input_index: {user_input_index}"})
            if len(store_choices) > 0:
                user_input = store_choices[0]  # Всегда используем первый элемент
                log_technical(get_user_uuid(user_id), "debug", details={"message": f"Using store_choices[0] = {user_input}"})
            else:
                # Если store_choices пуст, попробуем использовать удаленный магазин как исходный ввод
                if last_added_store:
                    user_input = last_added_store
                    log_technical(get_user_uuid(user_id), "debug", details={"message": f"Using removed store as input: {user_input}"})
                else:
                    user_input = ""
                    log_technical(get_user_uuid(user_id), "debug", details={"message": "No input found, using empty string"})
            
            similar = process.extract(
                user_input,
                ALL_STORES,
                limit=5,
                processor=str.lower,
            ) if process else []
            if not similar:
                response = reply("Не удалось найти похожие магазины. Попробуйте изменить запрос или ввести название вручную", disable_web_page_preview=True)
                duration = time.time() - start_time
                log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Не удалось найти похожие магазины. Попробуйте изменить запрос или ввести название вручную", "duration": duration})
                log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
                return JSONResponse(response)
            # Сохраняем варианты в user_data
            user_data["store_choices"] = [match[0] for match in similar]
            await set_user_data(user_id, user_data)
            log_technical(get_user_uuid(user_id), "debug", details={"message": f"Found {len(similar)} similar stores for '{user_input}': {[match[0] for match in similar]}"})
            log_technical(get_user_uuid(user_id), "debug", details={"message": f"After finding similar stores - stores: {user_data.get('stores', [])}, store_choices: {user_data.get('store_choices', [])}"})
            # Формируем кнопки с индексами
            buttons = [
                [{"text": match[0], "callback_data": f"pick_store::{i}"}] for i, match in enumerate(similar)
            ]
            keyboard = {"inline_keyboard": buttons}
            response = reply(f"Выберите правильный магазин для: <b>{user_input}</b>", keyboard, disable_web_page_preview=True)
            log_technical(get_user_uuid(user_id), "debug", details={"message": f"Final response - stores: {user_data.get('stores', [])}, store_choices: {user_data.get('store_choices', [])}"})
            duration = time.time() - start_time
            log_technical(get_user_uuid(user_id), "bot_response", details={"text": f"Выберите правильный магазин для: <b>{user_input}</b>", "duration": duration})
            log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
            return JSONResponse(response)

        # pick_store::<index>
        if callback_data.startswith("pick_store::"):
            log_technical(get_user_uuid(user_id), "debug", details={"message": f"Processing pick_store callback: {callback_data}"})
            index_str = callback_data.split("::")[1].strip() if len(callback_data.split("::")) > 1 else None
            if not index_str or not index_str.isdigit():
                response = reply("🏪 Не удалось определить магазин. Пожалуйста, выберите магазин из списка или попробуйте снова.", disable_web_page_preview=True)
                duration = time.time() - start_time
                log_technical(get_user_uuid(user_id), "bot_response", details={"text": "🏪 Не удалось определить магазин. Пожалуйста, выберите магазин из списка или попробуйте снова.", "duration": duration})
                log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
                return JSONResponse(response)
            index = int(index_str)
            log_technical(get_user_uuid(user_id), "debug", details={"message": f"Parsed index: {index}"})
            user_data = await get_user_data(user_id)
            store_choices = user_data.get("store_choices", [])
            log_technical(get_user_uuid(user_id), "debug", details={"message": f"pick_store - stores: {user_data.get('stores', [])}, store_choices: {store_choices}, index: {index}"})
            if index < 0 or index >= len(store_choices):
                response = reply("🏪 Не удалось определить магазин. Пожалуйста, выберите магазин из списка или попробуйте снова.", disable_web_page_preview=True)
                duration = time.time() - start_time
                log_technical(get_user_uuid(user_id), "bot_response", details={"text": "🏪 Не удалось определить магазин. Пожалуйста, выберите магазин из списка или попробуйте снова.", "duration": duration})
                log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
                return JSONResponse(response)
            chosen = store_choices[index]
            if chosen.lower() in [s.lower().strip() for s in user_data.get("stores", [])]:
                log_user_activity(get_user_uuid(user_id), "store_already_exists", {"store": chosen, "method": "callback_pick"})
                response = reply(f"🔁 Магазин <b>{chosen}</b> уже есть в списке", disable_web_page_preview=True)
                duration = time.time() - start_time
                log_technical(get_user_uuid(user_id), "bot_response", details={"text": f"🔁 Магазин <b>{chosen}</b> уже есть в списке", "duration": duration})
                log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
                return JSONResponse(response)
            user_data["stores"] = user_data.get("stores", []) + [chosen]
            await set_user_data(user_id, user_data)
            user_data = await get_user_data(user_id)
            log_user_activity(get_user_uuid(user_id), "store_added", {"store": chosen, "method": "callback_pick"})
            log_technical(get_user_uuid(user_id), "debug", details={"message": f"Added store '{chosen}', current stores: {user_data.get('stores', [])}"})
            log_technical(get_user_uuid(user_id), "debug", details={"message": f"After adding store - stores: {user_data.get('stores', [])}, store_choices: {user_data.get('store_choices', [])}"})
            response_text = f"<b>Магазин добавлен:</b> {chosen}\n\n"
            response_text += "<b>Текущий список:</b>\n"
            for i, store in enumerate(user_data["stores"], 1):
                response_text += f"{i}. {store}\n"
            # Две кнопки — каждая на своей строке
            # Для wrong_store передаём индекс исходного пользовательского ввода
            user_data = await get_user_data(user_id)
            store_choices = user_data.get("store_choices", [])
            # Находим индекс исходного пользовательского ввода
            original_input_index = len(store_choices) - 1 if store_choices else 0
            log_technical(get_user_uuid(user_id), "debug", details={"message": f"Added store '{chosen}', store_choices: {store_choices}, original_input_index: {original_input_index}"})
            keyboard = {"inline_keyboard": [
                [{"text": "❌ Это не тот магазин", "callback_data": f"wrong_store::0::{index}"}],
                [{"text": "💾 Сохранить запрос", "callback_data": "save_query"}]
            ]}
            response = reply(response_text, keyboard, disable_web_page_preview=True)
            duration = time.time() - start_time
            log_technical(get_user_uuid(user_id), "bot_response", details={"text": response_text, "duration": duration})
            log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
            return JSONResponse(response)

        # clear_list
        if callback_data == "clear_list":
            log_user_activity(get_user_uuid(user_id), "callback_action", {"action": "clear_list"})
            await set_user_data(user_id, {"stores": []})
            response = reply("Список магазинов очищен", disable_web_page_preview=True)
            duration = time.time() - start_time
            log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Список магазинов очищен", "duration": duration})
            log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
            return JSONResponse(response)

        # save_query
        if callback_data == "save_query":
            log_user_activity(get_user_uuid(user_id), "callback_action", {"action": "save_query_prompt"})
            user_data = await get_user_data(user_id)
            if not user_data.get("stores"):
                response = reply("Список магазинов пуст, нечего сохранять.", disable_web_page_preview=True)
                duration = time.time() - start_time
                log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Список магазинов пуст, нечего сохранять.", "duration": duration})
                log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
                return JSONResponse(response)
            await set_state(user_id, STATE_ENTERING_QUERY_NAME)
            response = reply("Введите название запроса:", disable_web_page_preview=True)
            duration = time.time() - start_time
            log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Введите название запроса:", "duration": duration})
            log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
            return JSONResponse(response)

        # load_query::<index>
        if callback_data.startswith("load_query::"):
            idx = int(callback_data.split("::")[1])
            queries = load_saved_queries(get_user_uuid(user_id))
            if idx >= len(queries):
                log_user_activity(get_user_uuid(user_id), "error", {"error": "query_index_out_of_range", "requested_index": idx, "available_count": len(queries)})
                response = reply("Не удалось найти выбранный запрос. Пожалуйста, выберите другой из списка.", disable_web_page_preview=True)
                duration = time.time() - start_time
                log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Не удалось найти выбранный запрос. Пожалуйста, выберите другой из списка.", "duration": duration})
                log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
                return JSONResponse(response)
            query = queries[idx]
            log_user_activity(get_user_uuid(user_id), "saved_queries_action", {"action": "load_by_callback", "query_index": idx, "query_name": query["name"]})
            # Сохраняем город, если он есть в запросе
            city = query.get("city")
            user_data = await get_user_data(user_id)
            new_data = {
                "stores": list(query["stores"]),
                "current_query_index": idx
            }
            if city:
                new_data["city"] = city
            else:
                # если в query нет города, оставляем старый
                if "city" in user_data:
                    new_data["city"] = user_data["city"]
            await set_user_data(user_id, new_data)
            await set_state(user_id, STATE_EDITING_SAVED_QUERY)
            response_text = f"Загружен список <b>{query['name']}</b>:\n\n"
            for i, store in enumerate(query["stores"], 1):
                response_text += f"{i}. {store}\n"
            response = reply(response_text, query_menu(), disable_web_page_preview=True)
            duration = time.time() - start_time
            log_technical(get_user_uuid(user_id), "bot_response", details={"text": response_text, "duration": duration})
            log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
            return JSONResponse(response)

        duration = time.time() - start_time
        log_technical(get_user_uuid(user_id), "processing_time", details={"handler": "handle_callback", "duration": duration})
        log_user_activity(get_user_uuid(user_id), "error", {"error": "unknown_callback", "callback_data": callback_data})
        response = reply("Кнопка устарела или больше не работает. Пожалуйста, обновите меню или начните сначала.", disable_web_page_preview=True)
        log_technical(get_user_uuid(user_id), "bot_response", details={"text": "Кнопка устарела или больше не работает. Пожалуйста, обновите меню или начните сначала.", "duration": duration})
        log_technical(get_user_uuid(user_id), "http_response", details={"status_code": 200, "status": "OK", "duration": duration})
        return JSONResponse(response)
        
    except HTTPException as e:
        duration = time.time() - start_time
        log_technical(None, "http_response", details={"status_code": e.status_code, "status": e.detail, "duration": duration})
        raise
    except Exception as e:
        duration = time.time() - start_time
        log_technical(None, "http_response", details={"status_code": 500, "status": "Internal Server Error", "error": str(e), "duration": duration})
        raise 