import uuid

NAMESPACE = uuid.UUID('d2a8b4b9-d4a1-4761-8568-2b34923e493a')

def get_user_uuid(telegram_id):
    """
    Генерирует детерминированный UUID5 для пользователя по Telegram ID.
    telegram_id: int или str
    return: str (UUID5)
    """
    return str(uuid.uuid5(NAMESPACE, str(telegram_id))) 