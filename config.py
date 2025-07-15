import os
from dotenv import load_dotenv

BOT_ENV = os.getenv("BOT_ENV", "prod")
if BOT_ENV == "test":
    load_dotenv(".env_test")
    print("Загружен .env_test")
else:
    load_dotenv(".env")
    print("Загружен .env")

BOT_TOKEN = os.getenv("BOT_TOKEN")
MALLS_FILE = os.getenv("MALLS_FILE")
ALIASES_FILE = os.getenv("ALIASES_FILE")
USER_MAP_FILE = os.getenv("USER_MAP_FILE")
USER_MAP_KEY_FILE = os.getenv("USER_MAP_KEY_FILE")
LOG_FILE = os.getenv("LOG_FILE")
USER_ACTIVITY_LOG_FILE = os.getenv("USER_ACTIVITY_LOG_FILE")
ERROR_LOG_FILE = os.getenv("ERROR_LOG_FILE")