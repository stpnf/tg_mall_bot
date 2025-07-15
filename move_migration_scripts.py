import os

scripts_to_delete = [
    'migrate_users_json.py',
    'migrate_stats_json.py',
    'migrate_saved_queries_json.py',
    'migrate_my_redis_log.py',
    'migrate_users_activity_json.py',
    'migrate_technical_json.py',
    'migrate_errors_json.py',
    'utils.py',
]

dir_name = 'migration_tools'

for script in scripts_to_delete:
    path = os.path.join(dir_name, script)
    if os.path.exists(path):
        os.remove(path)
        print(f'Deleted {path}')
    else:
        print(f'Not found: {path}') 