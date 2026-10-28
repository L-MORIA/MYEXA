# MYEXA — план исправления ошибок и недочётов

**Фокус:** адекватность поиска на всех языках (русский / английский / немецкий / итальянский).
**Дата анализа:** 28.10.2026
**База:** коммит `6cc95c7` (ветка `main`, рабочее дерево чистое до начала работы)

---

## ✅ Статус выполнения: план утверждён и реализован

Все 5 фаз выполнены и подтверждены тестами.

| Метрика | До | После |
|---|---|---|
| Тесты | 61 | **262** |
| Покрытие | 88 % | **98 %** |
| Ошибки ruff | 110 | **0** |
| Separation фильтра (ru / en / de / it) | +0.032 / +0.096 / −0.021 / −0.134 | **+0.308 / +0.334 / +0.309 / +0.312** |
| Recall на дефолтном пороге | — | **1.00** во всех 4 языках |
| Доменный фильтр для русского | 5 сайтов (hard) | **нет** (локализация через `userLocation`) |
| Ошибка провайдера | «0 результатов», `success: true` | **503 с причиной** |

**Что было сделано по фазам:**

- **Фаза 1** — `includeDomains` заменён на `userLocation` (код страны); сигнал Exa (`highlightScores`) возвращён в ранжирование (вес 25 %); `relevance_index` приведён к масштабу 0..1 (clamp `min(index, 1.0)`, на фронтенде — проценты); `publishedDate` из Exa теперь маппится и питает «свежесть», которая была мёртвым весом 15 %.
- **Фаза 2** — фильтр переписан: эмбеддится **заголовок** (0.7) + короткий сниппет (0.3), а не query-biased блок `highlights` на 4000 символов; порог 0.30 с возможностью per-language override и переопределения через API; пустой результат больше не маскируется под «всё подходит»; добавлены стратегии `title` / `blend` / `chunk`.
- **Фаза 3** — добавлен `lingua-language-detector==2.2.0`, ограниченный ru/en/de/it; `language_match` считается по детекции вместо константы 1.0; результаты на другом языке отсекаются (с мягким фолбэком, если совпадений меньше половины); доверенные домены стали per-language, сопоставление — по хосту, а не подстроке.
- **Фаза 4** — валидация входа (`num_results` 1..100, непустой запрос, порог 0..1, только известные языки → 400); `ExaError` вместо тихих нулей, `/api/search` отдаёт **503** с причиной, частичный отказ языка не теряет остальные; поиск по языкам **параллельный**; схема БД `UNIQUE(query, url)` + автоматическая миграция (проверена на реальной базе: 285 строк сохранены); `run.bat` убивает сервер по PID-файлу, а не все `python.exe`.
- **Фаза 5** — добавлен `GET /api/languages` (единственный источник правды), фронтенд строит чекбоксы и табы динамически; вкладка активирует реально выбранный язык; выбор языка OCR (по умолчанию `rus`); `pyproject.toml` с настройкой ruff и pytest; CI дополнен шагами `ruff check` и покрытием, `app.py` добавлен в `py_compile`; переводчик получил 3 попытки с backoff; удалена мёртвая зависимость `exa-py`; блокирующие `alert()` заменены inline-баннером (модальное окно замораживало страницу).

---

## 9. Инцидент: Exa API недоступен для IP этой машины (28.10.2026)

### Симптомы
`/api/search` возвращает **503 `Search backend unavailable: ru: Exa API error 403`**,
`/api/health?deep=true` → `degraded`.

### Диагностика (все шаги воспроизводимы)

| Проверка | Результат | Вывод |
|---|---|---|
| `curl` к `api.exa.ai` по IPv4 и IPv6 | 403 | не IPv6-специфично |
| Пустой payload `{}` | 403 | запрос не доходит до логики Exa |
| Старый payload (`includeDomains`) | 403 | мои изменения не причина |
| Новый payload (`userLocation`) | 403 | то же |
| Без `x-api-key`, с `Bearer`, с браузерным UA | 403 | не проблема авторизации |
| `GET /` на `api.exa.ai` | 403 | блок на весь хост |
| `exa.ai` (сайт), `api.cloudflare.com`, `www.cloudflare.com` | 200/301 | не общий блок Cloudflare |
| `api.exa.ai` и `docs.exa.ai` | 403 | правило WAF на конкретные хосты |
| DNS `api.exa.ai` (локальный, 1.1.1.1, 8.8.8.8) | 172.66.40.91 / 172.66.43.165, AS13335 Cloudflare | DNS не подменён |
| Все anycast-адреса через `--resolve` | 403 | не один «плохой» IP |
| `docs.exa.ai` в 12:20 — ок, позже 403 | эскалация | блок расширился во время диагностики |

**Итог:** бан по IP/ASN на edge Cloudflare для хостов `api.exa.ai` и `docs.exa.ai`.
Код приложения не участвует: блок возникает до разбора запроса.

### Хронология
- **08:04 и 09:18** — поиск у пользователя работал: в БД сохранено 36 и 15 результатов.
- **~12:05** — первые пробы к Exa уже дают 403 (код ещё не менялся).
- **12:20** — документация `docs.exa.ai` ещё открывается.
- **12:24** — проба на старом коде: 403 для всех 4 языков.
- **12:30+** — `docs.exa.ai` тоже отдаёт 403.

**Возможный вклад диагностики:** за окно 12:00–12:30 было выполнено ~30 запросов
к `api.exa.ai`. Блок с `api.exa.ai` на `docs.exa.ai` расширился именно в это окно,
поэтому нельзя исключить, что пробы подтолкнули Cloudflare к бану IP. Исключить это
не удалось.

### Что сделано в коде
- `Config.EXA_API_URL` — базовый URL Exa вынесен в настройку, чтобы провайдера можно
  было направить на зеркало или локальный стаб (`backend/config.py`, `backend/services/exa_service.py`).
- `backend/tests/test_pipeline_e2e.py` — полный конвейер против локального стаба Exa:
  перевод → поиск → фильтр → детекция языка → ранжирование. 5/5 зелёные.
  Это доказывает, что код исправен, а поломка — в доступе к провайдеру.
- **Мягкая деградация:** при полном отказе провайдера поиск по локальной БД
  продолжает работать, а причина отказа видна в `meta[<lang>].error`.
  503 поднимается только если не нашлось вообще ничего.

### План восстановления
1. **Ждать** — бан Cloudflare по IP обычно временный. Установлена автопроверка
   восстановления доступа.
2. **Фолбэк-провайдер: SearXNG** (свой инстанс, без внешних ключей) — выбран
   пользователем как запасной вариант, если блок не снимется.
   Замечание: DDG и Mojeek с этого IP отдают CAPTCHA, Brave и Bing отдают
   результаты, но без официального API это скрапинг.

---

## 0. Краткое резюме

Главная причина «русский ищется плохо, английский — нормально» **не в переводе и не в пороге
релевантности**. Перевод работает корректно, порог уже снижен до 0.3. Проблема в двух местах:

1. **Жёсткий доменный фильтр.** Для русского Exa получает `includeDomains` из 5 доменов
   (`lenta.ru`, `ria.ru`, `habr.com`, `vc.ru`, `tass.ru`), для английского — **пустой список**,
   то есть весь веб. `includeDomains` в Exa — это **hard constraint**, а не «подсказка».
   Русская выдача физически ограничена пятью сайтами (три из них — новостные ленты), английская
   не ограничена ничем. Асимметрия ровно та, что описывает пользователь.

2. **Фильтр релевантности измеряет не то.** Он эмбеддит полный блок `highlights` (~4000 символов)
   и сравнивает его с коротким запросом. Exa формирует `highlights` как **выдержки, подобранные
   под запрос**, поэтому блок цитирует запрос почти дословно — сравнение становится
   почти тавтологией. Измеренная сепарация «релевантное − нерелевантное»:

   | стратегия | ru | en | de | it |
   |---|---|---|---|---|
   | **сейчас: полный блок highlights** | **+0.032** | +0.096 | **−0.021** | **−0.134** |
   | заголовок + первые 600 символов | +0.100 | +0.208 | +0.102 | +0.020 |
   | только заголовок | **+0.420** | +0.412 | **+0.399** | **+0.439** |

   В русском фильтр отделяет нужное от ненужного на 0.03 — это шум. В немецком и итальянском
   separation **отрицательная**: нерелевантные результаты в среднем набирают **больше** очков,
   чем релевантные.

Дополнительно: ранжирование систематически занижает неанглийские результаты, а собственный
сигнал релевантности Exa (`highlightScores`) парсится — и **не используется** вообще.

---

## 1. Что было проверено и как

| Проверка | Результат |
|---|---|
| `pytest backend/tests` (до работы) | 61 passed, покрытие 88% |
| `pytest backend/tests` (после работы) | **153 passed, покрытие 98%** |
| `pytest` из `./backend` (как в CI) | 153 passed |
| `ruff check backend` | 110 ошибок, конфига ruff в репозитории нет |
| Живой перевод ru→en/de/it (Yandex) | **корректен**: `artificial intelligence in medicine`, `Künstliche Intelligenz in der Medizin`, `intelligenza artificiale in medicina` |
| Живой запрос к Exa (v4 и v6) | **403 Cloudflare на весь хост `api.exa.ai`** — включая `GET /`. `exa.ai` (сайт) отвечает 200, значит блокировка по IP/ASN, а не по ключу |
| Качество эмбеддинг-фильтра | измерено на реальной модели `paraphrase-multilingual-MiniLM-L12-v2`, таблица выше |
| Асимметрия ранжирования | измерено, `diagnostics/measured_ranking_asymmetry.txt` |

> **Блокер внешней проверки.** `api.exa.ai` недоступен с этой машины (Cloudflare WAF, egress
> 109.252.63.33 / 2a06:98c1:3123:8000::). Ключ `.env` не удалось провалидировать — 403 приходит
> раньше проверки ключа. Живое сравнение «до/после» нужно перепроверить из сети, где Exa
> доступен (VPN или другой egress).

---

## 2. Находки по приоритету

### P0 — ломает качество выдачи

#### P0-1. Доменный фильтр режет русскую выдачу до 5 сайтов
- **Где:** `backend/config.py:53` (`ru`), `:61` (`de`), `:65` (`it`); прокидывается в `backend/app.py:104-107`, уходит в payload в `backend/services/exa_service.py:41-42`.
- **Почему плохо:** `includeDomains` в Exa — hard constraint («If specified, results will only come from the matching domains or paths» — [Exa API reference](https://docs.exa.ai/reference/search)). Сам Exa в best practices прямо предупреждает использовать такие фильтры только когда результат вне фильтра непригоден. Три из пяти русских доменов (`ria.ru`, `tass.ru`, `lenta.ru`) — новостные ленты: на запрос про медицину или ML они дают новостные заметки, а не содержательные материалы. Английский (`config.py:57`) фильтр не имеет вовсе → ищет по всему вебу. **Это и есть асимметрия ru vs en.**
- **Дополнительно:** `de` ограничен 4 доменами, `it` — 3, причём `it.wikipedia.org` — это поддомен, а не национальный домен; при этом `en` не ограничен. Асимметрия воспроизводится во всех неанглийских языках.

#### P0-2. Фильтр релевантности эмбеддит query-biased блок и не различает релевантное
- **Где:** `backend/services/embedding.py:42` — `text = item.get("highlights", "") or item.get("title", "")`; highlights приходит с `maxCharacters: 4000` (`backend/services/exa_service.py:39`).
- **Почему плохо:** см. таблицу сепарации в §0. Фильтр пропускает почти всё (recall = 1.00) и при этом не отсеивает мусор → в выдаче много слабо-релевантного, а разброс между языками максимальный именно в русском.
- **Хуже:** `embedding.py:57-62` — если не прошёл хотя бы один, фильтр возвращает **все** элементы с нулевым `embedding_score`. То есть логика «ничего не нашлось» маскируется как «нашлось всё».

#### P0-3. Нет определения языка результата
- **Где:** `backend/services/indexing.py:29` — `language_score = 1.0  # Assume language already matched`.
- **Почему плохо:** язык результата нигде не проверяется. Вкладку «Русский» может наполнить английская выдача. Сейчас это частично замаскировано доменным фильтром P0-1; после его снятия станет критичным. Поле `language` в `services/exa_service.py:55` — это метка запрошенного языка, а не определённый язык документа.
- **Дополнительно:** `indexing.py:41-44` — список доверенных доменов полностью англоязычный (`github.com`, `stackoverflow.com`, `wikipedia.org`, `arxiv.org`, `medium.com`, `dev.to`, `docs.`). Любой результат с `wikipedia.org` (в т.ч. `de.wikipedia.org`, `ru.wikipedia.org`) получает максимум, а `lenta.ru`/`ria.ru`/`kommersant.ru` — 0.7. Это **систематический штраф всем неанглийским доменам** в ранжировании.

#### P0-4. Сигнал релевантности Exa парсится и выбрасывается
- **Где:** `backend/services/exa_service.py:53` кладёт `"score"` из `highlightScores`; `backend/services/indexing.py:16-18` его **не читает** — используется только `embedding_score`.
- **Почему плохо:** подтверждено замером: результат с `score=0.99` и `score=0.01` получают **идентичный** `relevance_index`. Exa уже посчитал релевантность — и она выброшена.

### P1 — ломает корректность и наблюдаемость

#### P1-1. `relevance_index` масштабируется как 0..1, а задокументирован как 0..100
- **Где:** `backend/services/indexing.py:9` (docstring «0-100»), `:36` (`min(index, 100.0)`).
- **Факт:** сумма весов `FilteringRules` = 0.40 + 0.20 + 0.15 + 0.15 + 0.10 = **1.00**. Максимум индекса — 1.0, а clamp на 100.0 никогда не срабатывает. Фронтенд показывает `(result.relevance_index || 0).toFixed(1)` (`frontend/index.html:98`) → пользователь видит «0.6», что читается как 0.6 из 100.
- **Побочно:** при максимуме float-сумма даёт `1.0000000000000002` — clamp на 1.0 тоже нужен.

#### P1-2. «Свежесть» — мёртвый вес 15% индекса
- **Где:** `backend/services/indexing.py:25` читает `result.get("created_at")`, но `services/exa_service.py:48-56` **не маппит** `publishedDate` из ответа Exa. Поле всегда `None` → `_calculate_freshness` всегда возвращает 0.5.
- **Почему плохо:** 15% веса ранжирования всегда константа. Exa возвращает `publishedDate` — данные есть, они просто теряются.

#### P1-3. Ошибки провайдеров молча превращаются в «0 результатов»
- **Где:** `backend/services/exa_service.py:24-26` — не-200 → `{}` → `search()` возвращает `[]`; `backend/app.py:147` всё равно отвечает `{"success": true}`.
- **Почему плохо:** при 403 Cloudflare пользователь видит «No results found», а не «сервис недоступен». Именно это состояние сейчас воспроизводится на этой машине.

#### P1-4. `num_results` не валидируется
- **Где:** `backend/models/schemas.py:7`, `backend/app.py:93`.
- **Почему плохо:** публичный лимит Exa — `numResults` ≤ 100 ([спецификация](https://docs.exa.ai/reference/search)). Фронтенд ограничивает 50, но API не ограничен: запрос `num_results=1000` уйдёт в Exa и вернёт 400, который превратится в «0 результатов» (P1-3). Значение ≤ 0 — тоже не отсекается.

#### P1-5. Неизвестные коды языков принимаются молча
- **Где:** `backend/models/schemas.py:6` — `languages: List[str]` без валидации; `backend/api/translator.py:45-47` — `LANG_MAP.get("fr")` → `None` → возвращается исходный текст.
- **Почему плохо:** `languages=["fr"]` → перевода нет, доменного фильтра нет, результаты помечаются `language: "fr"`. Пользователь получает русскую выдачу в «французской» вкладке без единого предупреждения.

#### P1-6. Поиск по языкам идёт строго последовательно
- **Где:** `backend/app.py:102-108` — цикл `for lang in languages` с сетевым вызовом внутри.
- **Почему плохо:** 4 языка × (Exa до 15 с + эмбеддинг) → до ~60 с. Запросы независимы — должны идти параллельно (`asyncio.gather` / `ThreadPoolExecutor`).

#### P1-7. `search_results.url` — UNIQUE глобально, а не в рамках запроса
- **Где:** `backend/api/database.py:30` — `url TEXT UNIQUE NOT NULL`; `save_result` глотает `IntegrityError` (`:62-63`).
- **Почему плохо:** один и тот же URL, найденный для разных запросов, сохраняется только один раз — с первым запросом. `get_results(query)` (`database.py:65`) фильтрует по точному `query`, поэтому для второго запроса history теряется, а `relevance_score`/`language` относятся к первому входу.

#### P1-8. `run.bat` убивает все процессы Python
- **Где:** `run.bat:39` — `taskkill /f /im python.exe`.
- **Почему плохо:** глушит любые посторонние Python-процессы пользователя (аналитика, ноутбуки, агенты), а не только сервер MYEXA. Нужен таргетный kill по PID.

#### P1-9. Фронтенд всегда переключается на вкладку «Русский»
- **Где:** `frontend/script.js:64` — `this.activeTab = 'Русский';` безусловно после поиска.
- **Почему плохо:** если русский не выбран, пользователь после поиска видит пустую вкладку вместо результатов выбранного языка.

### P2 — сопровождаемость и UX

#### P2-1. Реестр языков дублируется на фронтенде
- **Где:** `backend/config.py:50-67` (источник правды) ↔ `frontend/script.js:7,22-23` и `frontend/index.html:37-40`.
- **Почему плохо:** добавление языка требует правки 3 файлов + фронтовых хардкод-табов. Нет эндпоинта `/api/languages`. Нужен один источник правды.

#### P2-2. OCR всегда с `language: 'eng'`
- **Где:** `frontend/script.js:89` — `formData.append('language', 'eng')`; `backend/app.py:159` — дефолт `eng`.
- **Почему плохо:** русский скан проходит через `eng` → мусор. При этом бэкенд `language` пробрасывает корректно (`app.py:176`), т.е. фронтенд просто не даёт выбрать.

#### P2-3. `except:` в `_calculate_freshness`
- **Где:** `backend/services/indexing.py:76` — голый `except:` ловит и `KeyboardInterrupt`.

#### P2-4. `_calculate_domain_authority` ищет подстроку
- **Где:** `backend/services/indexing.py:46-48` — `if domain in url`. Совпадёт `notwikipedia.org` и `docs.` в любом URL.

#### P2-5. Состояние внешних сервисов не проверяется на старте
- **Где:** `backend/app.py:57-65` — сервисы инициализируются, но `/api/health` (`app.py:221`) всегда отвечает `{"status": "healthy"}`, независимо от доступности Exa и модели.

#### P2-6. Ruff не настроен; CI не проверяет линтер, покрытие и `app.py`
- **Где:** в репозитории нет `pyproject.toml` / `ruff.toml`; `ruff check backend` → 110 ошибок.
- **CI есть** (`.github/workflows/ci.yml`, коммит `6cc95c7`): ставит зависимости, гоняет
  `py_compile` по списку модулей, затем `pytest -v --tb=short -q` из `./backend`, проверяет
  наличие фронтовых файлов. Но:
  - `ruff` **не запускается** и **не установлен** (`backend/requirements-dev.txt` содержит
    только `pytest`, `pytest-asyncio`, `httpx`);
  - `pytest-cov` не подключён — покрытие в CI не измеряется;
  - в списке `py_compile` **нет `backend/app.py`** — самого главного модуля (проверено вручную:
    компилируется корректно, но в CI не защищено).

#### P2-7. Зависимость от неофициального endpoint
- **Где:** `backend/api/translator.py:17` — `translate.yandex.net/api/v1/tr.json/translate` (серая зона), `:20` — `googleapis.com/translate_a/single` ( unofficial).
- **Почему плохо:** оба могут отвалиться в любой момент. Сейчас работает, но без гарантий и без ретраев.

#### P2-8. `exa-py` установлен, но не используется
- **Где:** `backend/requirements.txt:5` — `exa-py==1.0.1`, при этом `services/exa_service.py` пишет сырой `requests`. Мёртвая зависимость (или недописанная миграция).

---

## 3. План исправлений

### Фаза 1 — убрать асимметрию выдачи (P0-1, P0-4, P1-1, P1-2)

**1.1 Заменить `includeDomains` на мягкое локализование.** Exa поддерживает `userLocation` —
двухбуквенный ISO 3166-1 код страны, который локализует выдачу
([спецификация](https://docs.exa.ai/reference/search)). Это даёт русскую выдачу **без** ограничения
списком доменов.

`backend/config.py` — заменить схему записи языка:
```python
LANGUAGES = {
    "ru": {"label": "Русский", "country": "RU", "include_domains": []},
    "en": {"label": "English", "country": "US", "include_domains": []},
    "de": {"label": "Deutsch", "country": "DE", "include_domains": []},
    "it": {"label": "Italiano", "country": "IT", "include_domains": []},
}
```
> `include_domains` остаётся в схеме как **пустой** optional-фильтр «жёсткого отбора» и по
> умолчанию пуст для всех языков. Смысл «предпочитать национальные источники» переносится в
> `userLocation` + формулировку запроса.

`backend/services/exa_service.py:29-45` — добавить в payload:
```python
if country:
    payload["userLocation"] = country
```
и **убрать** `includeDomains` из дефолтного пути (домены передаются только если явно заданы
пользователем).

`backend/app.py:104-107` — передавать `country`, а не домены:
```python
country = Config.language_country(lang)
results = exa_service.search(search_query, num_results, lang, country=country)
```

**1.2 Вернуть в ранжирование сигнал Exa.** `services/exa_service.py:48-56` — добавить
`"published_date": item.get("publishedDate")` и, при наличии, все `highlightScores`.
`backend/services/indexing.py:16-18` — считать `exa_score` как отдельный компонент веса,
например 25 %, сократив `relevance_score` (эмбеддинг) до 20 %.

**1.3 Починить масштаб индекса.** `backend/services/indexing.py:36` — `return min(index, 1.0)`;
docstring привести в соответствие («0..1»). Фронтенд `frontend/index.html:98` — умножать на 100
для отображения процента: `(result.relevance_index * 100).toFixed(1)`.

**1.4 Оживить свежесть.** `services/exa_service.py` — маппить `publishedDate`;
`indexing.py:25` — читать `published_date` (с fallback на `created_at`).

### Фаза 2 — сделать фильтр релевантности работающим (P0-2)

**2.1 Эмбеддить заголовок, а не query-biased блок.** `backend/services/embedding.py:42`:
```python
title = (item.get("title") or "").strip()
snippet = (item.get("highlights") or "")[:600].strip()
text = f"{title}. {snippet}" if title else snippet
```
Измеренный эффект: separation ru +0.032 → +0.100, de −0.021 → +0.102, it −0.134 → +0.020,
en +0.096 → +0.208; recall остаётся 1.00 во всех языках.

**2.2 Пересчитать порог под новую стратегию.** `backend/config.py:40` — базовое значение
**0.25**, с пер-language калибровкой (`thresholds = {"ru": 0.25, "en": 0.25, "de": 0.22, "it": 0.22}`)
после прогона на реальной выдаче. Порог должен стать **настраиваемым через API** (новое поле
`relevance_threshold` в `SearchQuery`).

**2.3 Убрать маскировку «пустого результата».** `backend/services/embedding.py:57-62` — если
ничего не прошло, возвращать пустой список и помечать результат флагом
`filtered_out=True`, чтобы UI показал «ничего не прошло порог», а не 10 слабых результатов.

**2.4 Добавить max-pooling по чанкам как опцию.** Для длинных highlights — считать
`max(sim(query, title), max over 500-char chunks)`; измерение: separation en +0.220, de +0.133
при recall 1.00. Реализовать как `EmbeddingService.score(query, item, strategy="title_chunk")`.

### Фаза 3 — определение языка (P0-3)

**3.1 Подключить детектор.** Добавить `lingua-language-detector==2.2.0` в
`backend/requirements.txt` (пакет доступен на PyPI, версия 2.2.0 проверена). Создать
`backend/services/language_detector.py`:
```python
class LanguageDetector:
    def detect(self, text: str) -> str | None: ...   # 'ru' | 'en' | 'de' | 'it' | None
    def match(self, text: str, target: str) -> float:  # 0..1
```
Детектировать по `title + highlights[:400]`.

**3.2 Считать реальный `language_match`.** `backend/services/indexing.py:28-30` — заменить
константу `1.0` на результат детекции: 1.0 при совпадении, 0.3 при несовпадении, 0.5 при
неопределённости.

**3.3 Отбирать результаты по языку.** В `backend/app.py` после эмбеддинг-фильтра — оставить
результаты с совпадающим языком; если их меньше половины — оставить и остальные (мягкое
поведение), но пометить `language_mismatch=True`, чтобы фронтенд мог их визуально отделить.

**3.4 Расширить доверенные домены по языкам.** `backend/services/indexing.py:41-44` — сделать
список per-language, добавив `ru.wikipedia.org`, `ru.mail.ru`, `expert.ru`, `kommersant.ru`,
`rbc.ru`, `meduza.io`, `nplus1.ru`, `polit.ru`, `vedomosti.ru`, `interfax.ru`, `iz.ru`,
`gazeta.ru`, `the-village.ru`, `vc.ru`, `habr.com`; `de`: `de.wikipedia.org`, `spiegel.de`,
`zeit.de`, `heise.de`, `golem.de`, `chip.de`, `c't`; `it`: `it.wikipedia.org`, `repubblica.it`,
`corriere.it`, `ilfattoquotidiano.it`, `repubblica.it`, `startpage`. Плюс: сравнивать по
 registrable-домену, а не подстроке (P2-4).

### Фаза 4 — надёжность и корректность API (P1-3…P1-7)

**4.1 Валидация входных данных.** `backend/models/schemas.py`:
```python
class SearchQuery(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    languages: List[str] = Field(default_factory=lambda: ["ru"], max_length=8)
    num_results: int = Field(default=10, ge=1, le=100)   # лимит Exa
    filter_by_relevance: bool = True
    search_custom_db: bool = True
    relevance_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
```
`backend/app.py` — отбрасывать коды не из `Config.LANGUAGES` с 400-ошибкой со списком
допустимых (P1-5).

**4.2 Проброс ошибок провайдера.** `backend/services/exa_service.py:17-27` — не глотать ошибки:
поднять доменное исключение `ExaError` с кодом и текстом; `backend/app.py` — возвращать
`503` с `detail` вместо «0 результатов» (P1-3). Добавить `GET /api/health?deep=1`, который
делает реальный пробный запрос к Exa и возвращает `degraded`, если он падает (P2-5).

**4.3 Параллельный поиск по языкам.** `backend/app.py:102-108` — заменить цикл на
`asyncio.gather` поверх `exa_service.search` (клиент — `requests`, поэтому обернуть в
`asyncio.to_thread` или перейти на `httpx.AsyncClient`). Ожидаемый выигрыш: 4 языка — с ~60 с
до ~15 с.

**4.4 Схема БД.** `backend/api/database.py:30` — заменить `url TEXT UNIQUE NOT NULL` на
`UNIQUE(query, url)` и добавить миграцию для существующей базы (SQLite: создать новую таблицу,
скопировать данные, переименовать). `save_result` — `INSERT ... ON CONFLICT(query, url) DO UPDATE`
(P1-7).

**4.5 `run.bat` — таргетный kill.** `run.bat:21` — сохранять PID сервера в файл; `run.bat:39` —
`taskkill /f /PID <pid>` вместо `/im python.exe` (P1-8). Дополнительно: проверить наличие
`EXA_API_KEY` и предупредить, если он пуст.

### Фаза 5 — фронтенд и сопровождаемость (P2-1…P2-8)

**5.1 Единый источник правды по языкам.** Добавить `GET /api/languages`, возвращающий
`Config.LANGUAGES` с `label`, `country`, `default`. `frontend/script.js` — загружать языки
из API, строить чекбоксы и табы динамически; убрать хардкод `tabs`/`tabKeyMap`
(`script.js:22-23`) и вычисляемое свойство `activeTabResults` (`:31-36`) — заменить на
`searchResults[activeLang]` по коду языка, а не по подписи (устраняет хрупкое сопоставление
`'Custom DB'`).

**5.2 Чинить переключение вкладок.** `frontend/script.js:64` — ставить активной вкладку
первого языка, реально выбранного пользователем, а не всегда «Русский» (P1-9).

**5.3 Выбор языка OCR.** `frontend/index.html` — добавить `<select>` для языка
Tesseract рядом с кнопкой OCR; `frontend/script.js:89` — брать значение из select; по
умолчанию `rus`, если в системе есть `rus.traineddata` (P2-2).

**5.4 Ruff + CI.** Добавить `pyproject.toml` с секцией `[tool.ruff]` (line-length 100,
target py311) и `backend/requirements-dev.txt` += `ruff`, `pytest-cov`. В
`.github/workflows/ci.yml` добавить шаг `ruff check backend` и `pytest --cov=backend`, а также
включить `backend/app.py` в список `py_compile` (P2-6).

**5.5 Перевод — ретраи и лимиты.** `backend/api/translator.py` — добавить 2 ретрая с
экспоненциальной задержкой, таймаут 5→8 с, кэш с TTL и ограничением размера (P2-7).
Рассмотреть переход на легальный `google-cloud-translate` (уже в requirements) как основной
канал, а неофициальные — как фолбэк.

**5.6 Убрать мёртвую зависимость.** Удалить `exa-py==1.0.1` из `requirements.txt` либо
мигрировать на официальный SDK (P2-8).

---

## 4. Новые тесты (добавить вместе с фиксами)

| Файл | Тест | Что фиксирует |
|---|---|---|
| `test_config.py` | `test_ru_has_no_default_domain_filter` | P0-1: у `ru` не должно быть доменного фильтра по умолчанию |
| `test_config.py` | `test_every_language_has_country_code` | P0-1: у каждого языка есть ISO-код страны для `userLocation` |
| `test_exa_service.py` | `test_user_location_sent_to_payload` | P0-1: `userLocation` попадает в payload |
| `test_exa_service.py` | `test_include_domains_not_sent_by_default` | P0-1: `includeDomains` отсутствует, если явно не задан |
| `test_exa_service.py` | `test_published_date_is_parsed` | P1-2: `publishedDate` извлекается |
| `test_exa_service.py` | `test_highlight_scores_all_preserved` | P0-4: все `highlightScores`, а не только первый |
| `test_embedding.py` | `test_uses_title_not_full_highlights` | P0-2: в эмбеддинг идёт заголовок, а не 4000-символьный блоб |
| `test_embedding.py` | `test_relevant_outranks_irrelevant_in_all_languages` | P0-2: на размеченном корпусе релевантное должно быть выше нерелевантного **для ru/en/de/it** (регрессия на главный баг) |
| `test_embedding.py` | `test_empty_result_not_masked_as_full_list` | P0-2: пустой фильтр возвращает пустой список, а не всё |
| `test_language_detector.py` | `test_detects_ru_en_de_it` | P0-3: детектор работает на 4 языках |
| `test_indexing.py` | `test_language_match_uses_detection` | P0-3: `language_match` не константа |
| `test_indexing.py` | `test_domain_authority_per_language` | P0-3: у русских доменов нет системного штрафа |
| `test_indexing.py` | `test_index_max_is_one` | P1-1: индекс в 0..1 |
| `test_indexing.py` | `test_exa_score_contributes_to_index` | P0-4: `score` влияет на индекс |
| `test_app_api.py` | `test_rejects_unsupported_language` | P1-5: 400 на неизвестный код |
| `test_app_api.py` | `test_rejects_num_results_above_exa_limit` | P1-4: 422 при `num_results > 100` |
| `test_app_api.py` | `test_returns_503_when_exa_down` | P1-3: ошибка провайдера не маскируется под «0 результатов» |
| `test_app_api.py` | `test_parallel_language_search` | P1-6: языки ищутся параллельно |
| `test_database.py` | `test_same_url_saved_for_two_queries` | P1-7: URL уникален в паре (query, url) |

**Существующий тест, который нужно инвертировать:**
`backend/tests/test_app_api.py:118-140` (`test_search_calls_exa_with_domains`) сейчас **закрепляет
дефектное поведение** — требует, чтобы для `ru` в `include_domains` был `lenta.ru`. После Фазы 1
этот тест должен быть заменён на проверку мягкой локализации.

---

## 5. Критерии приёмки

1. `pytest backend/tests` — все тесты зелёные; добавлены ≥ 20 новых тестов из §4; покрытие ≥ 95%.
2. `ruff check backend` — 0 ошибок; конфиг `pyproject.toml` в репозитории.
3. На размеченном корпусе (`diagnostics/embedding_quality.py`): separation
   `rel_mean − irr_mean` ≥ 0.25 для **каждого** из ru/en/de/it; recall ≥ 0.95.
4. В выдаче Exa для русского запроса доля русскоязычных документов ≥ 80 % (сейчас не
   измеряется — нет детекции).
5. `includeDomains` в payload не приходит ни для одного языза по умолчанию; вместо этого
   приходит `userLocation`.
6. При недоступности Exa API `/api/search` возвращает 503, а не пустой список с
   `success: true`.
7. Поиск по 4 языкам завершается быстрее, чем последовательный вариант (замерить: 1 язык vs 4).
8. `relevance_index` ∈ [0, 1]; на фронтенде отображается в процентах.
9. `run.bat` при остановке не убивает посторонние процессы Python.
10. Живая проверка качества — из сети с доступом к `api.exa.ai` (с текущей машины заблокировано).

---

## 6. Порядок работ и оценка

| Фаза | Содержание | Файлы | Оценка |
|---|---|---|---|
| 1 | Локализация вместо доменного фильтра, сигналы Exa, масштаб индекса, свежесть | `config.py`, `exa_service.py`, `indexing.py`, `app.py`, `index.html` | 3–4 ч |
| 2 | Рабочий фильтр релевантности | `embedding.py`, `config.py`, `schemas.py` | 3 ч |
| 3 | Определение языка | новый `services/language_detector.py`, `indexing.py`, `app.py`, `requirements.txt` | 4–5 ч |
| 4 | Валидация, ошибки, параллельность, БД | `schemas.py`, `app.py`, `exa_service.py`, `database.py`, `run.bat` | 4–5 ч |
| 5 | Фронтенд, ruff/CI, перевод | `script.js`, `index.html`, `translator.py`, `pyproject.toml`, `.github/` | 4–5 ч |

**Фазы 1 и 2 дают основной эффект для жалобы «русский ищется плохо».** Фаза 3 обязательна,
если Фаза 1 снимает доменный фильтр — иначе вкладка «Русский» наполнится иноязычными
документами.

---

## 7. Приложения

| Файл | Содержание |
|---|---|
| `diagnostics/live_probe.py` | живой прогон перевода и Exa (с/без доменных фильтров) |
| `diagnostics/embedding_quality.py` | измерение качества фильтра на реальной модели, 4 стратегии × 4 языка |
| `diagnostics/strategy_sweep.py` | перебор стратегий × порогов — выбор production-конфигурации фильтра |
| `diagnostics/ranking_asymmetry.py` | измерение асимметрии ранжирования по доменам |
| `diagnostics/detector_probe.py` | сравнение конфигураций детектора языка |
| `diagnostics/db_inspect.py` | проверка схемы БД и миграции на реальной базе |
| `diagnostics/probe_upload.py` | проверка видимости `content-length` для multipart-части |
| `diagnostics/measured_*.txt` | сохранённые результаты измерений |
| `backend/tests/relevance_corpus.py` | размеченный корпус — общий для тестов и замеров |

---

## 8. Что изменено на диске в рамках анализа

**Изменены (тесты, логика не трогалась):**

| Файл | Что сделано |
|---|---|
| `backend/tests/test_app_api.py` | +13 тестов: пути ошибок (500 по всем сервисам), дефолты, сохранение в БД, отключение фильтра/custom_db, гард размера файла (multipart собирается вручную, т.к. httpx не ставит per-part Content-Length), проброс языка в OCR |
| `backend/tests/test_embedding.py` | +5 тестов: `calculate_similarity` на реальном `pytorch_cos_sim`, сбой эмбеддинга одного элемента, приоритет `highlights` над `title`, `batch_filter` |
| `backend/tests/test_exa_service.py` | +12 тестов: HTTP-слой `_request` (заголовки, non-200, таймаут, исключение), `search_multiple_languages`, парсинг `publishedDate`/`highlightScores` |
| `backend/tests/test_translator.py` | +6 тестов: сетевые исключения Yandex/Google, битый JSON, пустой `text` от Yandex |
| `backend/tests/test_indexing.py` | +7 тестов: все ветки `_calculate_freshness`, масштаб индекса, игнорирование `score` Exa |

**Созданы:**

| Файл | Покрытие |
|---|---|
| `backend/tests/test_site_db.py` | `services/site_db.py` 29% → **100%** |
| `backend/tests/test_ocr_service.py` | `services/ocr_service.py` 30% → **100%** (модуль был без тестов полностью) |
| `backend/tests/test_config.py` | `config.py` 88% → **100%**, реестр языков, разбор порта |
| `diagnostics/*.py`, `diagnostics/*.txt` | инструменты и результаты измерений |

**Что НЕ менялось:** production-код (`app.py`, `config.py`, `translator.py`, `exa_service.py`,
`embedding.py`, `indexing.py`, `site_db.py`, `ocr_service.py`, `database.py`, `schemas.py`),
фронтенд, `run.bat`, `requirements*.txt`. Все правки из §3 — в плане, а не в коде.

**Известное ограничение тестов:** все тесты мокируют внешние сервисы. Ни один тест не проверяет
качество выдачи Exa на живом API — это принципиально невозможно, пока `api.exa.ai` недоступен
из этой сети (403 Cloudflare). Регрессионный тест на качество релевантности из §4 заменяет эту
слепую зону офлайн-корпусом.
