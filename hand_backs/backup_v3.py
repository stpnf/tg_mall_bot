import json
import os
import asyncio
from rapidfuzz import process
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram import Router
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN

USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)  # Должен быть список []
    return []

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def update_user_info(user: types.User):
    users = load_users()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Проверяем, есть ли уже такой пользователь по id
    existing = next((u for u in users if u["id"] == user.id), None)

    if existing:
        existing["last_active"] = now
    else:
        users.append({
            "id": user.id,
            "username": user.username or "",
            "first_name": user.first_name or "",
            "join_date": now,
            "last_active": now
        })

    save_users(users)

# Загружаем malls.json
with open("malls.json", "r", encoding="utf-8") as f:
    MALLS_DATA = json.load(f)

# Загружаем aliases.json
with open("aliases.json", "r", encoding="utf-8") as f:
    STORE_ALIASES = json.load(f)

# Получаем список всех магазинов из базы
ALL_STORES = set()
for city_data in MALLS_DATA.values():
    for mall in city_data.values():
        ALL_STORES.update(mall["stores"])
ALL_STORES = list(ALL_STORES)

# FSM
class Form(StatesGroup):
    choosing_city = State()
    entering_store = State()

user_data = {}

WELCOME_TEXT = """
<b>Добро пожаловать в MallFinder 🛍️</b>

Этот бот поможет вам найти торговые центры, где есть нужные вам магазины.

🛒 Просто:
1. Выберите город
2. Введите названия магазинов
3. Получите список ТЦ с этими магазинами (с адресами и этажами)

<b>Работают сокращения и синонимы названий!</b>
"""


def correct_store_name(user_input, all_known_stores, aliases_threshold=70, stores_threshold=70):
    input_lower = user_input.strip().lower()

    # 1. Чёткое совпадение по алиасам
    for official_name, aliases in STORE_ALIASES.items():
        if input_lower in [a.lower() for a in aliases]:
            return official_name

    # 2. Чёткое совпадение по списку магазинов
    for store in all_known_stores:
        if store.lower() == input_lower:
            return store

    # 3. Только если ничего не найдено — fuzzy
    match = process.extractOne(user_input, all_known_stores, score_cutoff=stores_threshold)
    return match[0] if match else None


def search_store_variants_in_mall(user_query, stores_dict):
    # Ищет все магазины с похожими именами (например, с уточнением здания)
    user_query_lower = user_query.lower()
    matches = [
        (store_name, floor)
        for store_name, floor in stores_dict.items()
        if user_query_lower in store_name.lower()
    ]
    return matches


# Бот
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Меню
def city_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Москва"), KeyboardButton(text="Санкт-Петербург")],
        [KeyboardButton(text="⬅️ Назад")]
    ], resize_keyboard=True)

def after_store_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Добавить"), KeyboardButton(text="🔍 Искать")],
        [KeyboardButton(text="🧾 Редактировать"), KeyboardButton(text="🔁 Сменить город")]
    ], resize_keyboard=True)


# Команды

@router.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    update_user_info(message.from_user)
    uid = message.from_user.id
    user_data[uid] = {"city": None, "stores": []}
    await message.answer(WELCOME_TEXT)
    await message.answer("Привет! Выбери город:", reply_markup=city_menu())
    await state.set_state(Form.choosing_city)

async def change_city(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    user_data[uid] = {"city": None, "stores": []}
    await message.answer("Выберите город:", reply_markup=city_menu())
    await state.set_state(Form.choosing_city)


@router.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(WELCOME_TEXT)


@router.message(Form.choosing_city)
async def choose_city(message: types.Message, state: FSMContext):
    city = message.text.strip()
    if city not in MALLS_DATA:
        await message.answer("Пока доступны только Москва и Санкт-Петербург.")
        return

    user_data[message.from_user.id]["city"] = city
    user_data[message.from_user.id]["stores"] = []
    await state.set_state(Form.entering_store)

    await message.answer(
        f"Вы выбрали город: <b>{city}</b>.\n\n"
        "Теперь вы можете:\n"
        "➕ Добавить — ввести название магазина\n"
        "🔍 Искать — найти ТЦ с нужными магазинами\n"
        "🧾 Редактировать — посмотреть или удалить магазины\n\n"
        "Введите название магазина",
        reply_markup=after_store_menu()
    )

@router.message(Form.entering_store)
async def handle_store_input(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    text = message.text.strip()
    update_user_info(message.from_user)

    # Если пользователь случайно снова ввёл название города
    if text in MALLS_DATA:
        await message.answer(
            f"❗ Вы уже выбрали город: <b>{user_data[message.from_user.id]['city']}</b>.\n\n"
            "Если вы хотите <b>сменить город</b> — нажмите 🔁 Сменить город.\n\n"

            "Если хотите продолжить — введите название магазина:"
        )
        return

    # Показываем список
    if text == "🧾 Редактировать":
        stores = user_data[uid]["stores"]
        if not stores:
            await message.answer("Список пуст.")
        else:
            response = "<b>Ваш список магазинов:</b>\n"
            for i, store in enumerate(stores, 1):
                response += f"{i}. {store}\n"
            response += "\nЧтобы удалить магазин — отправь его номер."
            await message.answer(response)
        return

    # Удаление по номеру
    if text.isdigit():
        index = int(text) - 1
        stores = user_data[uid]["stores"]
        if 0 <= index < len(stores):
            removed = stores.pop(index)
            await message.answer(f"Магазин <b>{removed}</b> удалён из списка.", reply_markup=after_store_menu())
        else:
            await message.answer("❌ Неверный номер.")
        return

    # Сменить город
    if text == "🔁 Сменить город":
        await change_city(message, state)
        return

    # Поиск
    if text == "🔍 Искать":
        await perform_search(message)
        return

    # Добавить
    if text == "➕ Добавить":
        await message.answer("Введите название магазина:")
        return

    # Назад — вернуться к выбору города
    if text == "⬅️ Назад":
        await state.set_state(Form.choosing_city)
        await message.answer("Выберите город:", reply_markup=city_menu())
        return




    # Попробуем найти исправленное название
    corrected = correct_store_name(text, ALL_STORES)

    if not corrected:
        await message.answer(f"❌ Магазин <b>{text}</b> не найден. Попробуйте снова.")
        return

    # Проверим на дубликаты
    if corrected.lower() in [s.lower() for s in user_data[uid]["stores"]]:
        await message.answer(f"🔁 Магазин <b>{corrected}</b> уже есть в списке.")
        return

    # Добавляем
    user_data[uid]["stores"].append(corrected)

    # Показываем актуальный список
    response = "<b>Магазин добавлен:</b> " + corrected + "\n\n"
    response += "<b>Текущий список:</b>\n"
    for i, store in enumerate(user_data[uid]["stores"], 1):
        response += f"{i}. {store}\n"

    await message.answer(response, reply_markup=after_store_menu())


# Поиск ТЦ

async def perform_search(message):
    user_id = message.from_user.id
    city = user_data[user_id].get("city")
    if not city:
        await message.answer("Сначала выберите город через /start.")
        return

    queries = user_data[user_id].get("stores", [])
    if not queries:
        await message.answer("Сначала добавьте магазины для поиска.")
        return

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

            if mall_name.strip().lower() == "мега белая дача":
                variants = search_store_variants_in_mall(corrected_query, mall_stores_dict)
                if variants:
                    # добавляем только если имя точно совпадает
                    for name, floor in variants:
                        if name.lower() == corrected_query.lower():
                            matched_stores.append((name, floor))
                            found_store_queries.add(store_query.lower())
            else:
                for store_lower, (original_store, floor) in mall_stores_lower.items():
                    if corrected_query.lower() == store_lower:
                        matched_stores.append((original_store, floor))
                        found_store_queries.add(store_query.lower())
                        break

        if matched_stores:
            results.append((mall_name, mall_data["address"], matched_stores, mall_data, len(found_store_queries)))

    if not results:
        await message.answer("Магазины не найдены 😔")
        return

    results.sort(key=lambda x: len(x[2]), reverse=True)

    total_user_selected = len(queries)
    full_response = ""

    for mall, address, matched_stores, mall_data, matched_count in results:
        yandex_link = mall_data.get("map_link") or f"https://yandex.ru/maps/?text={address.replace(' ', '+')}"
        # Удаляем дубликаты магазинов по (название, этаж)
        matched_stores = list({(name, floor) for name, floor in matched_stores})
        matched_stores.sort(key=lambda x: (x[1] is None, x[1]))

        text = f"🏬 <b>{mall}</b> — {matched_count} / {total_user_selected} магазинов\n"
        text += f"<a href='{yandex_link}'>{address}</a>\n\n"

        for name, floor in matched_stores:
            floor_info = f" — {floor} этаж" if floor is not None else ""
            text += f"• {name}{floor_info}\n"

        full_response += text + "\n"

    await message.answer(full_response.strip(), disable_web_page_preview=True)

@router.message()
async def fallback_handler(message: types.Message, state: FSMContext):
    user_state = await state.get_state()

    # Если пользователь ни разу не запускал /start
    uid = message.from_user.id
    if uid not in user_data:
        await start(message, state)
        return

    # Иначе — просто проигнорировать или дать подсказку
    await message.answer("⚠️ Пожалуйста, нажмите /start, чтобы начать.")

# Запуск
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))