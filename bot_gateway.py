import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import aiohttp
from config import BOT_TOKEN
from aiogram.types import LinkPreviewOptions
import os

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in environment variables!")

LOGIC_API_URL = "http://localhost:8000/handle_update"
LOGIC_API_CALLBACK_URL = "http://localhost:8000/handle_callback"
API_TOKEN = os.getenv("API_TOKEN")
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

def dict_to_reply_markup(markup_dict):
    if not markup_dict:
        return None
    if "inline_keyboard" in markup_dict:
        # InlineKeyboardMarkup
        return types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(**btn) for btn in row]
                for row in markup_dict["inline_keyboard"]
            ]
        )
    if "keyboard" in markup_dict:
        # ReplyKeyboardMarkup
        return types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(**btn) for btn in row]
                for row in markup_dict["keyboard"]
            ],
            resize_keyboard=markup_dict.get("resize_keyboard", True),
            is_persistent=markup_dict.get("is_persistent", True)
        )
    return None

@dp.message()
async def handle_message(message: types.Message):
    async with aiohttp.ClientSession() as session:
        payload = {
            "user_id": message.from_user.id if message.from_user else None,
            "username": message.from_user.username if message.from_user else None,
            "first_name": message.from_user.first_name if message.from_user else None,
            "text": message.text,
            "chat_id": message.chat.id,
        }
        async with session.post(LOGIC_API_URL, json=payload, headers=HEADERS) as resp:
            data = await resp.json()
            reply_markup = dict_to_reply_markup(data.get("reply_markup"))
            link_preview_options = None
            if data.get("disable_web_page_preview"):
                link_preview_options = LinkPreviewOptions(is_disabled=True)
            await message.answer(
                data["text"],
                reply_markup=reply_markup,
                link_preview_options=link_preview_options
            )

@dp.callback_query()
async def handle_callback_query(callback: types.CallbackQuery):
    async with aiohttp.ClientSession() as session:
        payload = {
            "user_id": callback.from_user.id if callback.from_user else None,
            "callback_data": callback.data,
            "message_id": callback.message.message_id if callback.message else None,
            "chat_id": callback.message.chat.id if callback.message else None,
        }
        async with session.post(LOGIC_API_CALLBACK_URL, json=payload, headers=HEADERS) as resp:
            data = await resp.json()
            reply_markup = dict_to_reply_markup(data.get("reply_markup"))
            link_preview_options = None
            if data.get("disable_web_page_preview"):
                link_preview_options = LinkPreviewOptions(is_disabled=True)
            if callback.message:
                await callback.message.answer(
                    data["text"],
                    reply_markup=reply_markup,
                    link_preview_options=link_preview_options
                )
        await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 