# Описание системы для ИТ-службы

## 1. Назначение

`Ecookna QualAnalize` - сервис автоматической проверки заказов на оконные конструкции по PDF-выгрузке. Сервис предоставляет:

- Telegram-бота для отправки PDF и получения отчета;
- веб-интерфейс для подбора формул и проверки PDF;
- детерминированную проверку на стороне PostgreSQL;
- интеграцию со справочниками Directus.

## 1.1. Боевые реквизиты

- Web-интерфейс: [https://fastcheck.entechai.ru](https://fastcheck.entechai.ru)
- Telegram-бот: [@testecooknabot](https://t.me/testecooknabot)
- Directus: [https://rules.entechai.ru](https://rules.entechai.ru)
- PostgreSQL DSN: `postgresql+asyncpg://entechai:<DB_PASSWORD>@46.173.20.149:5433/entechai`



## 2. Актуальный эксплуатационный контур

По коду репозитория актуальный рабочий контур состоит из следующих компонентов:

- `bot` - Telegram-бот на `aiogram`;
- `web` - HTTP API и web UI на `FastAPI`;
- `frontend` - SPA на `React 19 + Vite + TypeScript`;
- `PostgreSQL` - хранение данных и выполнение контрольной логики;
- `Directus` - источник справочников `films` и `art_rules`.

## 3. Технологический стек

### 3.1. Backend

- Python 3.11
- FastAPI
- Uvicorn
- aiogram 3
- SQLAlchemy 2 + asyncpg
- pdfplumber
- pydantic-settings

### 3.2. Frontend

- React 19
- TypeScript
- Vite 7
- Tailwind CSS 4
- shadcn/ui
- Radix UI
- lucide-react

### 3.3. Data layer

- PostgreSQL
- SQL functions / triggers / tables
- Directus REST API

## 4. Логическая архитектура

### 4.1. Вариант работы через веб

1. Пользователь открывает веб-интерфейс.
2. Для подбора формулы frontend вызывает `POST /api/slip-formulas`.
3. Backend округляет размеры, ищет запись в `size_control` и возвращает допустимые формулы.
4. Для проверки PDF frontend вызывает `POST /api/check` с файлом.
5. Backend сохраняет PDF во временный файл, извлекает текст через `pdfplumber`, парсит позиции, выполняет анализ и записывает результаты в БД.
6. Пользователю возвращается JSON с итогом и деталями по проблемным позициям.

### 4.2. Вариант работы через Telegram

1. Пользователь отправляет PDF боту.
2. Бот скачивает файл через Telegram API.
3. Backend разбирает PDF и создает записи в БД.
4. Для каждой позиции выполняется проверка.
5. Бот отправляет текстовый отчет в чат.

## 5. Структура репозитория

- `bot/` - Telegram-бот, бизнес-логика на Python, модели SQLAlchemy.
- `web/` - FastAPI-приложение и fallback-шаблон.
- `frontend/` - SPA и UI-компоненты.
- `scripts/tables/` - DDL таблиц.
- `scripts/procedures/` - SQL-функции и триггерные функции.
- `scripts/triggers/` - фрагменты привязки триггеров.
- `docs/examples/` - примеры PDF.

## 6. Используемые таблицы и коллекции

### 6.1. Коллекции Directus, реально используемые кодом

#### `films`

Назначение:

- справочник пленок;
- используется для фильтрации пленок при разборе формулы;
- признак `type_of_film = "для триплекса"` влияет на объединение стекол в триплекс.

Ключевые поля по модели и SQL:

- `id`
- `films_article`
- `films_type`
- `type_of_film`
- `date_created`
- `date_updated`

Использование в коде:

- backend загружает коллекцию через Directus API `GET /items/films`;
- данные кэшируются в `Analyzer._films_cache`.

#### `art_rules`

Назначение:

- справочник стекол;
- используется для определения признаков стекла, в том числе закалки.

Ключевые поля по модели и SQL:

- `id`
- `glass_article`
- `glass_type`
- `type_of_glass`
- `type_of_processing`
- `surface`
- `note`
- `analog_list`

Использование в коде:

- backend загружает коллекцию через Directus API `GET /items/art_rules`;
- данные кэшируются в `Analyzer._articles_cache`;
- поле `type_of_processing` используется как дополнительный источник признака "закаленное".

### 6.2. Основные таблицы PostgreSQL

#### `size_control`

Назначение:

- таблица правил слипания;
- поиск ведется по округленным размерам;
- для каждой записи могут быть заданы допустимые формулы по 1, 2 и 3 камерам.

Ключевые поля:

- `dim1`, `dim2`
- `marking`
- `formula_1_1k`, `formula_2_1k`
- `formula_1_2k`, `formula_2_2k`
- `formula_1_3k`, `formula_2_3k`

#### `qual_analize_files`

Назначение:

- журнал обработанных файлов;
- хранение имени файла, источника, Telegram-метаданных и фрагмента исходного текста.

#### `qual_analize_pos`

Назначение:

- хранение позиций заказа;
- хранение исходных размеров, округленных размеров, формулы, раскладки, JSON исходных данных позиции;
- фиксация итогового статуса и допустимых формул `f1`/`f2`.

#### `qual_analize_pos_issues`

Назначение:

- хранение всех ошибок и предупреждений по позиции;
- хранение машинно-обрабатываемого `context`.

#### `qual_analize_rules`

Назначение:

- справочник правил валидации;
- в текущем рабочем Python-коде напрямую не используется.

#### `qual_analize_prompts`

Назначение:

- упоминается в `README.md`;
- в текущем рабочем Python-коде не используется.

## 7. Переменные окружения

Сервис использует следующие переменные окружения.

### 7.1. Обязательные

#### `BOT_TOKEN`

- токен Telegram-бота;
- обязателен для запуска `bot`.

#### `DB_DSN`

- DSN подключения к PostgreSQL в async-формате SQLAlchemy;
- пример структуры:
  `postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>`
- используется и `bot`, и `web`.
- боевое значение:
  `postgresql+asyncpg://entechai:<DB_PASSWORD>@46.173.20.149:5433/entechai`

#### `DIRECTUS_URL`

- базовый URL Directus;
- ожидается без завершающего `/`;
- пример:
  `https://rules.entechai.ru`

#### `DIRECTUS_TOKEN`

- Bearer-токен для доступа к коллекциям Directus.

### 7.2. Необязательные

#### `LOG_LEVEL`

- уровень логирования;
- значение по умолчанию: `INFO`.

### 7.3. Структура `.env`

Рекомендуемый шаблон:

```dotenv
BOT_TOKEN=telegram_bot_token
DB_DSN=postgresql+asyncpg://entechai:<DB_PASSWORD>@46.173.20.149:5433/entechai
DIRECTUS_URL=https://rules.entechai.ru
DIRECTUS_TOKEN=directus_api_token
LOG_LEVEL=INFO
```

### 7.4. Особенности

- frontend не использует отдельные переменные окружения на runtime;
- backend загружает `.env` через `pydantic-settings`;
- лишние переменные допускаются и игнорируются (`extra='ignore'`).

## 8. Развертывание

### 8.1. Минимальные зависимости

Нужны:

- PostgreSQL с загруженной схемой проекта;
- Directus с доступом к коллекциям `films` и `art_rules`;
- Python 3.11;
- Node.js для сборки frontend;
- Docker и Docker Compose, если используется контейнерный запуск.

### 8.2. Подготовка БД

В БД должны быть созданы:

- таблицы из `scripts/tables/`;
- функции из `scripts/procedures/`.

Критично для работы:

- `size_control`
- `qual_analize_files`
- `qual_analize_pos`
- `qual_analize_pos_issues`
- `check_slip`
- `check_argon`
- `check_missing_glass`
- `check_slip_tempered`
- `recalc_overall`
- `parse_order_elements`
- `parse_order_elements_full`
- `parse_slip_formula`
- `reset_pos_issues`
- `trg_calc_qual_pos`
- `trg_qual_checks_after`

### 8.3. Замечание по триггерам

В репозитории есть триггерные функции, но в `scripts/triggers/` лежат только фрагменты `EXECUTE FUNCTION ...`, без полного `CREATE TRIGGER`.

Вывод по коду:

- система рассчитывает поля позиции до записи;
- затем после записи запускает полный набор проверок.

Это означает, что в БД должны быть вручную созданы триггеры на таблицу `qual_analize_pos`. Предположительно:

- `BEFORE INSERT OR UPDATE` -> `trg_calc_qual_pos()`
- `AFTER INSERT OR UPDATE` -> `trg_qual_checks_after()`

Это вывод из логики функций, а не готовый SQL из репозитория. Перед промышленным внедрением привязку триггеров нужно оформить отдельным DDL-скриптом и проверить на тестовой базе.

### 8.4. Локальный запуск без Docker

1. Создать `.env`.
2. Установить Python-зависимости:

```bash
pip install -r requirements.txt
```

3. Собрать frontend:

```bash
cd frontend
npm install
npm run build
```

4. Запустить web:

```bash
uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload
```

5. Запустить Telegram-бота отдельным процессом:

```bash
python -m bot.main
```

### 8.5. Развертывание через Dockerfile

По предоставленным данным, целевой способ развертывания - через `Dockerfile`.

В репозитории также присутствует `docker-compose.yml`, который может использоваться как вспомогательный локальный сценарий, но базовым артефактом развертывания следует считать именно [Dockerfile](/Users/romangaleev/CodeProject/Ecookna/Ecookna_QualAnalize/Dockerfile).

Базовая схема развертывания:

1. Собрать образ из `Dockerfile`.
2. Передать в контейнер `.env` или эквивалентный набор переменных окружения.
3. Запустить один контейнер с [entrypoint.sh](/Users/romangaleev/CodeProject/Ecookna/Ecookna_QualAnalize/entrypoint.sh), который поднимает bot и web внутри одного runtime.

Особенности текущего репозитория:

- `Dockerfile` собирает Python-окружение и копирует проект в `/app`;
- `entrypoint.sh` запускает bot и web в одном контейнере;
- `docker-compose.yml` задает альтернативный сценарий с отдельными сервисами `bot` и `web`;
- web по умолчанию слушает `8000` внутри контейнера.

Принятый production-вариант:

- один контейнер с `entrypoint.sh`.

### 8.6. Важное замечание по frontend в Docker

`web.app` отдает `frontend/dist/index.html`, если каталог `frontend/dist` существует. Иначе используется fallback-шаблон `web/templates/index.html`.

Следствие:

- для полноценного UI frontend должен быть заранее собран;
- текущий `Dockerfile` не содержит шагов `npm install` и `npm run build`;
- если frontend не собран, будет отдан fallback HTML, а не SPA.

Для продуктивного развертывания нужно либо:

- собирать frontend вне контейнера и включать `frontend/dist` в образ;
- либо расширить `Dockerfile` мультистейдж-сборкой frontend.

## 9. Сетевые взаимодействия

### 9.1. Внешние зависимости

- Telegram Bot API
- Directus REST API
- PostgreSQL

### 9.1.1. Известные боевые адреса

- публичный web URL: `https://fastcheck.entechai.ru`
- Directus URL: `https://rules.entechai.ru`
- Telegram-бот: `@testecooknabot`
- PostgreSQL host: `46.173.20.149`
- PostgreSQL port: `5433`
- PostgreSQL database: `entechai`

### 9.2. HTTP API сервиса

#### `GET /`

- отдает собранный frontend или fallback HTML.

#### `POST /api/slip-formulas`

- вход: JSON с полем `size`;
- формат значения: `1520*2730`, допускаются также `x`, `х`, `×`;
- выход: найденные формулы или сообщение `not_found`.

#### `POST /api/check`

- вход: multipart/form-data, поле `file`;
- ограничение по коду: принимаются только PDF;
- выход: JSON со статусом проверки и списком проблемных позиций.

## 10. Хранение и обработка данных

### 10.1. Что сохраняется

В БД сохраняются:

- факт обработки файла;
- фрагмент полного текста PDF;
- все извлеченные позиции;
- JSON полезной нагрузки позиции;
- найденные ошибки и контекст.

### 10.2. Что не реализовано как отдельный файловый архив

- исходный PDF в БД не сохраняется;
- в `file_path` для Telegram хранится `file_id`, для web - строка `web_upload`.

## 11. Мониторинг и эксплуатационные риски

### 11.1. Наблюдаемые риски по коду

- отсутствие полного DDL для `CREATE TRIGGER` в репозитории;
- отсутствие автоматической сборки frontend в `Dockerfile`;
- в web-сценарии справочник `art_rules` не подгружается, а в Telegram-сценарии подгружается;
- проверка размера файла `10 МБ` указана только в UI и не enforced на backend;
- клиент Directus использует `verify_ssl=False` в `Analyzer`, что недопустимо без отдельного решения по безопасности для production.
- в предоставленных эксплуатационных данных пока отсутствуют документированные реквизиты подключения к PostgreSQL и точный production runtime-сценарий контейнера.

### 11.2. Что проверить перед вводом в эксплуатацию

- актуальность схемы БД;
- наличие и работоспособность триггеров;
- доступность Directus и корректность токена;
- корректность Telegram-токена;
- наличие собранного `frontend/dist`;
- успешную обработку реального эталонного PDF.

## 12. Полезные внутренние ссылки

- [README](/Users/romangaleev/CodeProject/Ecookna/Ecookna_QualAnalize/README.md)
- [docker-compose.yml](/Users/romangaleev/CodeProject/Ecookna/Ecookna_QualAnalize/docker-compose.yml)
- [Dockerfile](/Users/romangaleev/CodeProject/Ecookna/Ecookna_QualAnalize/Dockerfile)
- [bot/config.py](/Users/romangaleev/CodeProject/Ecookna/Ecookna_QualAnalize/bot/config.py)
- [web/app.py](/Users/romangaleev/CodeProject/Ecookna/Ecookna_QualAnalize/web/app.py)
- [bot/services/analyzer.py](/Users/romangaleev/CodeProject/Ecookna/Ecookna_QualAnalize/bot/services/analyzer.py)
- [bot/services/directus.py](/Users/romangaleev/CodeProject/Ecookna/Ecookna_QualAnalize/bot/services/directus.py)
- [bot/database/models.py](/Users/romangaleev/CodeProject/Ecookna/Ecookna_QualAnalize/bot/database/models.py)
- [scripts/tables/size_control.sql](/Users/romangaleev/CodeProject/Ecookna/Ecookna_QualAnalize/scripts/tables/size_control.sql)
- [scripts/procedures/check_slip.sql](/Users/romangaleev/CodeProject/Ecookna/Ecookna_QualAnalize/scripts/procedures/check_slip.sql)
- [scripts/procedures/trg_calc_qual_pos.sql](/Users/romangaleev/CodeProject/Ecookna/Ecookna_QualAnalize/scripts/procedures/trg_calc_qual_pos.sql)
- [scripts/procedures/trg_qual_checks_after.sql](/Users/romangaleev/CodeProject/Ecookna/Ecookna_QualAnalize/scripts/procedures/trg_qual_checks_after.sql)
