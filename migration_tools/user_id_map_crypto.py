import uuid
import json
import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Подгружаем переменные окружения для поддержки тестовой среды
BOT_ENV = os.getenv("BOT_ENV", "prod")
if BOT_ENV == "test":
    load_dotenv(".env_test")
else:
    load_dotenv(".env")

NAMESPACE_UUID = uuid.UUID("d2a8b4b9-d4a1-4761-8568-2b34923e493a")
KEY_FILE = os.getenv("USER_MAP_KEY_FILE", "user_map.key")
ENC_FILE = os.getenv("USER_MAP_FILE", "user_map.enc")
USER_MAP_SECRET = os.getenv("USER_MAP_SECRET")


def get_or_create_key():
    if USER_MAP_SECRET:
        return USER_MAP_SECRET.encode()
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
    else:
        with open(KEY_FILE, "rb") as f:
            key = f.read()
    return key


def load_mapping():
    key = get_or_create_key()
    fernet = Fernet(key)
    if not os.path.exists(ENC_FILE):
        return {}
    with open(ENC_FILE, "rb") as f:
        encrypted = f.read()
        if not encrypted:
            return {}
        decrypted = fernet.decrypt(encrypted)
        return json.loads(decrypted.decode("utf-8"))


def save_mapping(mapping):
    key = get_or_create_key()
    fernet = Fernet(key)
    data = json.dumps(mapping, ensure_ascii=False).encode("utf-8")
    encrypted = fernet.encrypt(data)
    with open(ENC_FILE, "wb") as f:
        f.write(encrypted)


def get_user_uuid(user_id):
    return str(uuid.uuid5(NAMESPACE_UUID, str(user_id)))


def add_mapping(user_id):
    mapping = load_mapping()
    user_id_str = str(user_id)
    uuid5 = get_user_uuid(user_id)
    if user_id_str not in mapping:
        mapping[user_id_str] = uuid5
        save_mapping(mapping)
        print(f"Добавлен: {user_id_str} -> {uuid5}")
    else:
        print(f"Уже есть: {user_id_str} -> {uuid5}")
    return uuid5


def get_uuid(user_id):
    mapping = load_mapping()
    return mapping.get(str(user_id))


def get_user_id(uuid5):
    mapping = load_mapping()
    for user_id, uuid_val in mapping.items():
        if uuid_val == uuid5:
            return user_id
    return None


def export_mapping(filename="user_map_decrypted.json"):
    mapping = load_mapping()
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"Экспортировано в {filename}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="User ID <-> UUID5 mapping tool (encrypted)")
    parser.add_argument("--add", type=str, help="Add user_id to mapping")
    parser.add_argument("--get-uuid", type=str, help="Get UUID5 for user_id")
    parser.add_argument("--get-user-id", type=str, help="Get user_id for UUID5")
    parser.add_argument("--export", action="store_true", help="Export mapping to user_map_decrypted.json")
    args = parser.parse_args()

    if args.add:
        add_mapping(args.add)
    if args.get_uuid:
        print(get_uuid(args.get_uuid))
    if args.get_user_id:
        print(get_user_id(args.get_user_id))
    if args.export:
        export_mapping() 