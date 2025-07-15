# Нормализация названий магазинов

В этой папке хранятся все вспомогательные файлы для нормализации и унификации названий магазинов в malls.json и aliases.json.

## Как проверить и нормализовать новые магазины после добавления ТЦ

1. **Добавьте новые ТЦ** в malls.json обычным способом (через парсеры или вручную).
2. **Перейдите в папку normalization_results:**
   ```bash
   cd normalization_results
   ```
3. **Запустите скрипт нормализации:**
   ```bash
   python3 normalize_store_names.py
   ```
   - Скрипт соберёт все уникальные магазины, сгруппирует их по нормализованному виду и выберет эталонные названия.
   - Итоговые файлы: `store_group_map_normalized.json`, `store_groups_normalized.json`.
   - Топ-20 спорных случаев — в `ambiguous_groups_preview.json`.
4. **Проверьте файл ambiguous_groups_preview.json** — если есть спорные случаи, скорректируйте их вручную в malls.json или aliases.json.
5. **Примените автозамену эталонов во всех ТЦ:**
   ```bash
   python3 apply_store_normalization.py
   ```
   - Будет сделана резервная копия malls.json.
   - Все варианты магазинов будут приведены к эталонным названиям.
   - aliases.json также будет нормализован.

---

## Файлы
- `store_group_map_normalized.json` — итоговый маппинг для автозамены
- `store_groups_normalized.json` — группы по нормализованному виду
- `ambiguous_groups_preview.json` — топ-20 спорных случаев для ручной проверки
- `normalize_store_names.py` — скрипт для группировки и нормализации
- `apply_store_normalization.py` — скрипт для массовой автозамены

## Рекомендация
**Делайте резервную копию malls.json перед массовой заменой!** 