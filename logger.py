# logger.py
import json
import os
from datetime import datetime

TECHNICAL_LOG = "logs/technical.json"
ERROR_LOG = "logs/errors.json"
USER_ACTIVITY_LOG = "logs/users_activity.json"

def log_event(user_id, event, details=None):
    data = {
        "user_id": user_id,
        "event": event,
        "timestamp": datetime.now().isoformat(timespec="seconds")
    }
    if details:
        data.update(details)

    # Определяем, в какой лог писать
    if event.startswith("error"):
        log_file = ERROR_LOG
    elif event in ["city_selected", "store_added", "query_saved", "query_renamed", "query_deleted", "query_stores_updated", "store_search"]:
        log_file = USER_ACTIVITY_LOG
    else:
        log_file = TECHNICAL_LOG

    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            try:
                stats = json.load(f)
            except Exception:
                stats = []
    else:
        stats = []

    stats.append(data)

    try:
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        # Если не удалось записать лог — пробуем записать ошибку в технический лог
        if log_file != TECHNICAL_LOG:
            try:
                with open(TECHNICAL_LOG, "a", encoding="utf-8") as f:
                    f.write(f"LOGGING ERROR: {e} | DATA: {data}\n")
            except Exception:
                pass

def log_technical(user_id, event, details=None):
    data = {
        "user_id": user_id,
        "event": event,
        "timestamp": datetime.now().isoformat(timespec="seconds")
    }
    if details:
        data.update(details)
    log_file = TECHNICAL_LOG
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            try:
                stats = json.load(f)
            except Exception:
                stats = []
    else:
        stats = []
    stats.append(data)
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        try:
            with open(TECHNICAL_LOG, "a", encoding="utf-8") as f:
                f.write(f"LOGGING ERROR: {e} | DATA: {data}\n")
        except Exception:
            pass

def log_user_activity(user_id, event, details=None):
    data = {
        "user_id": user_id,
        "event": event,
        "timestamp": datetime.now().isoformat(timespec="seconds")
    }
    if details:
        data.update(details)
    log_file = USER_ACTIVITY_LOG
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            try:
                stats = json.load(f)
            except Exception:
                stats = []
    else:
        stats = []
    stats.append(data)
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        try:
            with open(TECHNICAL_LOG, "a", encoding="utf-8") as f:
                f.write(f"LOGGING ERROR: {e} | DATA: {data}\n")
        except Exception:
            pass
