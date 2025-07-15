# User ID <-> UUID5 Mapping Tool (Encrypted)

Этот инструмент позволяет хранить соответствия между Telegram user_id и UUID5 в зашифрованном виде.

## Файлы
- `user_map.enc` — зашифрованный mapping-файл (user_id <-> UUID5)
- `user_map.key` — ключ для расшифровки mapping-файла
- `user_map_decrypted.json` — расшифрованный mapping-файл (создаётся только при экспорте)

## Использование

```bash
# Добавить пользователя (user_id -> UUID5)
python migration_tools/user_id_map_crypto.py --add 123456789

# Получить UUID5 по user_id
python migration_tools/user_id_map_crypto.py --get-uuid 123456789

# Получить user_id по UUID5
python migration_tools/user_id_map_crypto.py --get-user-id 8e87e1fa-0bd8-5e2c-91b6-6218f7dd9f43

# Экспортировать mapping в user_map_decrypted.json
python migration_tools/user_id_map_crypto.py --export
```

## Интеграция в бота

В коде бота при первом появлении пользователя вызывайте функцию `add_mapping(user_id)`, чтобы добавить соответствие в mapping-файл.

## Безопасность
- Храните `user_map.key` отдельно и не публикуйте его.
- Не храните `user_map_decrypted.json` постоянно, используйте только для поддержки. 