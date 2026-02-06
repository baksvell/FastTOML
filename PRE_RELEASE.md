# Чек-лист перед выкладкой (PyPI / релиз)

**Репозиторий:** [git@github.com:baksvell/FastTOML.git](https://github.com/baksvell/FastTOML)

## Уже сделано

- [x] Парсер: таблицы, массивы таблиц, inline-таблицы, даты/время, многострочные строки, Unicode
- [x] **dumps() / dump()** — сериализация dict → TOML (реализация на Python)
- [x] Совместимость с tomli (тесты на одном TOML)
- [x] Бенчмарки (fasttoml vs tomli)
- [x] Обработка ошибок: некорректный TOML → `ValueError`, без падений
- [x] Улучшения валидации: integer (leading zero), float (double-dot, leading/trailing dot), datetime (offset, day-in-month, trailing dot) — где нужно, отклоняем невалидный ввод
- [x] Интеграция toml-test: pytest-тесты по официальному набору (valid: 152 с 9 пропусками по формату; invalid: ограниченный набор)
- [x] CI: сборка и тесты на Windows / Linux / macOS, Python 3.10–3.12 (без бенчмарков в CI)
- [x] README: установка, примеры, ограничения, тесты и бенчмарки
- [x] `pyproject.toml`: лицензия SPDX, метаданные, опциональные зависимости dev

## Выложено на PyPI

- Пакет доступен: `pip install fasttoml`
- Страница: https://pypi.org/project/fasttoml/

## Рекомендуется перед первым стабильным релизом (1.0)

1. **Инициализация Git и привязка к GitHub** (если новый клон)  
   - Если репозиторий ещё не инициализирован:  
     `git init`  
   - Добавить remote:  
     `git remote add origin git@github.com:baksvell/FastTOML.git`  
   - Добавить файлы, коммит, пуш в `main`:  
     `git add .` → `git commit -m "..."` → `git push -u origin main`

2. **Прогнать CI**  
   После пуша убедиться, что GitHub Actions проходят на всех платформах (Windows / Linux / macOS, Python 3.10–3.12).

3. **Проверить сборку локально**  
   - `python setup.py build_ext --inplace`  
   - `pytest tests/ -v --ignore=tests/test_benchmark.py`

4. **Перед публикацией на PyPI (beta)**  
   - Установить: `pip install build twine`  
   - Собрать: `python -m build`  
   - Проверить установку из `dist/*.whl` в чистом venv.  
   - Загрузить (после настройки PyPI-аккаунта и токена):  
     `twine upload dist/*`  
   - Для многих платформ (Windows/Linux/macOS, разные Python) позже можно добавить cibw (e.g. `cibuildwheel`) в отдельный workflow.

## Улучшения на будущее (после PyPI)

- **Бейджи в README** — CI, PyPI, License ✅
- **Строгая валидация дат** ✅ — месяц 01–12, день по календарю (включая високосный год), час 00–23, минута/секунда 00–59 (секунда до 60 для leap second), запрет мусора после даты/времени (например `1979-01-01x`)
- **Доп. escape в строках** ✅ — в basic string поддерживаются все последовательности TOML 1.0: `\b` `\t` `\n` `\f` `\r` `\"` `\\` `\uXXXX` `\UXXXXXXXX`; невалидные (например `\x`, `\z`) приводят к `ValueError`
- **Полный прогон invalid toml-test** ✅ — по умолчанию 200 invalid-кейсов, с TOML_TEST_INVALID_FULL=1 все 473; список известных «принятых» (129) в _INVALID_ACCEPTED_SKIP, тест падает только при принятии кейса вне списка
- **cibuildwheel** ✅ — workflow `.github/workflows/wheels.yml`: сборка wheels на Ubuntu/Windows/macOS (Python 3.10–3.12), запуск вручную (workflow_dispatch) или при публикации release; артефакты загружаются в Actions (загрузку на PyPI можно добавить через секрет)
- **CHANGELOG.md** — вести историю версий для пользователей ✅
- **CONTRIBUTING.md** ✅ — инструкция для контрибьюторов (сборка, тесты, PR)

## Команды для проверки перед релизом

```bash
# Сборка
python setup.py build_ext --inplace

# Все тесты (без бенчмарков)
pytest tests/ -v --ignore=tests/test_benchmark.py

# Бенчмарки (локально)
pytest tests/test_benchmark.py -v --benchmark-only

# Установка в режиме разработки
pip install -e .[dev]

# Сборка пакета для PyPI
python -m build
```
