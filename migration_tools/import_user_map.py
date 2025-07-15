import json
from cryptography.fernet import Fernet

KEY_FILE = "user_map.key"
ENC_FILE = "user_map.enc"
DECRYPTED_FILE = "user_map_decrypted.json"

with open(KEY_FILE, "rb") as f:
    key = f.read()
fernet = Fernet(key)

with open(DECRYPTED_FILE, "r", encoding="utf-8") as f:
    mapping = json.load(f)

data = json.dumps(mapping, ensure_ascii=False).encode("utf-8")
encrypted = fernet.encrypt(data)

with open(ENC_FILE, "wb") as f:
    f.write(encrypted)

print("user_map.enc обновлён!") 