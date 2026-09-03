# Recruitment Service — API-контракт и рекомендации по UI

Этот документ — для разработчика CRM. Описывает, как CRM должна интегрироваться с
Recruitment Service, и какой UI имеет смысл реализовать в CRM для работы с этим
функционалом.

## Принцип

**Recruitment Service ничего не пишет в CRM.** Он владеет своими данными (найденные
кандидаты, их источники, оценки, шаблоны поиска) в собственной Postgres и отдаёт их
через HTTP API. CRM сама решает, когда и что забирать, и сама создаёт свои
`Candidate`/`Application` из этих данных.

```
CRM frontend → CRM backend → Recruitment Service API → своя Postgres
```

Frontend CRM никогда не должен ходить в Recruitment Service напрямую — только через
свой backend (иначе `INTERNAL_SERVICE_TOKEN` утечёт в браузер).

## Подключение

- Base URL внутри Docker-сети: `http://recruitment-api:8000`
- Все эндпоинты, кроме `/health` и `/providers/hh/callback`, требуют заголовок:
  ```
  Authorization: Bearer <INTERNAL_SERVICE_TOKEN>
  ```
  Токен — общий секрет, задан в `.env` Recruitment Service. Без него — `401`.
- Интерактивная документация (Swagger UI) доступна из той же Docker-сети:
  `http://recruitment-api:8000/docs`

---

## 1. Шаблоны поиска — `/search-templates`

Шаблон поиска — это то, что HR настраивает для одной вакансии: критерии подбора,
включён ли автопоиск и с каким интервалом.

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/search-templates` | Список всех шаблонов |
| `POST` | `/search-templates` | Создать шаблон |
| `GET` | `/search-templates/{id}` | Получить один шаблон |
| `PUT` | `/search-templates/{id}` | Частично обновить |
| `DELETE` | `/search-templates/{id}` | Удалить |
| `POST` | `/search-templates/{id}/run` | Запустить поиск (см. раздел 2) |

### Тело запроса (`POST`/`PUT`)

```json
{
  "name": "Media Buyer (Facebook, iGaming)",
  "crm_vacancy_id": "vac-123",
  "is_active": true,
  "auto_search_enabled": true,
  "interval_minutes": 60,
  "score_thresholds": { "medium": 55, "high": 75, "hot": 90 },
  "criteria": [
    { "key": "vertical", "value": "igaming", "mode": "required", "weight": 0 },
    { "key": "technology", "value": "Keitaro", "mode": "preferred", "weight": 10 }
  ]
}
```

- `crm_vacancy_id` — просто строка-ссылка на вакансию в CRM. Recruitment Service её не
  валидирует, использует только как ключ для сопоставления при отдаче кандидатов
  (`GET /external-candidates?search_template_id=...`) и при приёме Telegram-откликов.
- `interval_minutes` — только если `auto_search_enabled: true`; допустимые значения:
  **15, 30, 60, 120, 360, 720, 1440** (15м/30м/1ч/2ч/6ч/12ч/24ч). Любое другое
  значение — `422`.
- `PUT` — частичное обновление: поле, которое не прислали (или `null`), не
  меняется. Исключение — `criteria`: если прислать `[]`, все критерии удалятся; если
  не прислать поле вообще — критерии останутся как были.

### Критерии — `criteria[]`

```json
{ "key": "employment_type", "value": "full", "mode": "required", "weight": 0 }
```

- `mode`: `required` | `preferred` | `ignore`
- `weight`: 0–100, имеет смысл только для `preferred`

#### Несколько альтернатив в одном критерии — `|`

`value` может содержать несколько вариантов через `|` — означает «совпадает **любой**
из перечисленных». Работает одинаково и для HH-фильтров, и для scoring.

```json
{ "key": "position", "value": "Media Buyer|Facebook Media Buyer|Traffic Manager", "mode": "required", "weight": 0 }
{ "key": "job_search_status", "value": "active_search|looking_for_offers", "mode": "required", "weight": 0 }
```

Примеры использования:
- Синонимы должности («Media Buyer» / «Facebook Media Buyer» / «Traffic Manager»)
- Группа статусов поиска работы («активно ищет» ИЛИ «рассматривает предложения»)
- Группа GEO через `geo` (свободный текст) — например `"USA|UK|Canada|Australia"` для
  «Tier-1»; **но** это просто список стран, которые CRM должна собрать сама на своей
  стороне (никакого встроенного понятия «Tier-1»/«LATAM» у нас нет — см. раздел «Чего
  пока нет»).

Для структурных полей (`employment_type`, `work_format`, `job_search_status`,
`geo_area_id`, `professional_role_id`, `salary_from`/`salary_to`) каждая альтернатива
проверяется отдельно — HH это поддерживает нативно (несколько значений одного
параметра). Невалидные альтернативы (опечатка, не из списка допустимых) молча
пропускаются, остальные всё равно применяются.

**Важно — HR не должна видеть эти технические `key`/`value` напрямую.** UI CRM должен
показывать HR человеческие названия и списки выбора, а сам транслировать их в
конкретные `key`/`value` из таблицы ниже. Recruitment Service сам решает, какой
критерий станет реальным фильтром поиска HH.ru, а какой — только участвует в подсчёте
score — HR это тоже не должно заботить.

#### Распознаваемые `key` (структурные критерии)

| `key` | Допустимые `value` | Что делает `required` | Как участвует в scoring |
|---|---|---|---|
| `experience_level` | `no_experience`, `1_3_years`, `3_6_years`, `6_plus_years` | Фильтр HH `experience` | Порог по общему стажу (0/12/36/72 мес.) |
| `min_experience_months` | число (месяцы) | — (только scoring) | Точный порог по стажу, `preferred` даёт частичный балл пропорционально |
| `employment_type` | `full`, `part_time`, `internship`, `volunteer` | Фильтр HH `employment_form` | Точное совпадение |
| `work_format` | `on_site`, `remote`, `hybrid`, `field_work`, `fly_in_fly_out` | Фильтр HH `work_format` | Точное совпадение |
| `job_search_status` | `active_search`, `looking_for_offers`, `not_looking_for_job`, `has_job_offer`, `accepted_job_offer` | Фильтр HH `job_search_status` | Точное совпадение |
| `geo_area_id` | числовой ID региона HH (напр. `"1"` = Москва) | Фильтр HH `area` | не участвует напрямую |
| `geo` | произвольный текст (город/страна) | — (только scoring) | Подстрока в названии региона кандидата |
| `professional_role_id` | числовой ID роли HH | Фильтр HH `professional_role` | не участвует напрямую |
| `salary_from` / `salary_to` | число | Фильтр HH `salary_from`/`salary_to` | Сравнение с зарплатным ожиданием |
| `language` | `"eng"` или `"eng:b2"` (код + опц. уровень) | Фильтр HH `language`, только если указан уровень (`code:level`) | Код без уровня — совпадение по языку; с уровнем — точный уровень |
| `recent_experience_months` | число (месяцы) | — (только scoring) | «Опыт не старше N месяцев» — required режет по порогу |

Любой другой `key` (например `vertical`, `traffic_source`, `technology` — то, чего нет
как отдельного поля в HH, вроде «iGaming», «Facebook», «Keitaro», «PWA») —
воспринимается как **ключевое слово**:
- `required` → обязательный AND-термин в полнотекстовом поиске HH + должен буквально
  встретиться в тексте резюме/анкеты кандидата.
- `preferred` → попадает в OR-группу полнотекстового поиска (расширяет охват) и даёт
  балл, если слово встретилось в тексте резюме/анкеты — без исключения кандидатов, не
  содержащих его.

**Принципиально:** `preferred`-критерий **никогда** не становится жёстким фильтром
поиска HH (даже структурный) — иначе «желательный» критерий начал бы вести себя как
обязательный. Только `required` может исключить кандидата из поиска или провалить его
по `hard_filters_passed`.

### Scoring

```
score = round(100 × Σ(weight × match_fraction) / Σ(weight))   — по всем preferred-критериям
```

Веса не обязаны суммироваться в 100 — пересчитывается пропорционально. Если
`preferred`-критериев нет вообще — `score = 0`.

Тиры по умолчанию (переопределяются через `score_thresholds`):

| Score | Tier |
|---|---|
| 0–54 | `low` |
| 55–74 | `medium` |
| 75–89 | `high` |
| 90–100 | `hot` |

`hard_filters_passed = false`, если хотя бы один `required`-критерий не выполнен —
такой кандидат всё равно попадёт в `/external-candidates`, но CRM может (и должна)
показывать его иначе / скрывать по умолчанию.

---

## 2. Запуск поиска — `/search-runs`

```
POST /search-templates/{id}/run  →  202
{ "search_run_id": "...", "status": "queued" }
```

Поиск **не выполняется синхронно** — воркер подхватит задачу асинхронно. Дальше нужно
поллить статус:

```
GET /search-runs/{run_id}  →  200
{
  "id": "...",
  "search_template_id": "...",
  "trigger": "manual",           // или "scheduled"
  "status": "completed",         // queued | running | completed | failed
  "started_at": "...",
  "finished_at": "...",
  "stats": {
    "found": 42, "new": 10, "known": 32,
    "passed_hard_filters": 25, "above_threshold": 8
  },
  "error_message": null,
  "created_at": "..."
}
```

`GET /search-runs?search_template_id={id}` — история запусков по конкретному шаблону.

Автопоиск (`auto_search_enabled: true`) создаёт такие же `search_run` (с
`trigger: "scheduled"`) сам, без вызова CRM — планировщик встроен в воркер
Recruitment Service.

---

## 3. Кандидаты — `/external-candidates`

**Это основной эндпоинт для CRM.** Здесь забираются найденные и оценённые кандидаты —
из HH и (когда подключим Telegram-бота) из Telegram.

Каждая находка (результат поиска или входящий отклик) проходит **единый шлюз
триажа** — `review_status`: `pending` → `added` / `skipped`. Это не HR-пайплайн найма
(интервью/оффер/отказ — полностью в CRM), а только бинарное решение «эту находку HR
уже разобрала или нет». Экраны «🔎 Поиск кандидатов» и «📩 Отклики» в UI — это, по
сути, один и тот же список с `review_status=pending`, просто с разными фильтрами
сверху; «👤 Кандидаты» — список с `review_status=added`.

```
GET /external-candidates?search_template_id={id}&min_score=55&source=hh&review_status=pending&limit=50&offset=0
```

Параметры (все опциональны):
- `source` — `hh` | `telegram`
- `search_template_id` — только кандидаты, оценённые по этому шаблону
- `min_score` — только с score ≥ N (0–100)
- `review_status` — `pending` | `added` | `skipped`
- `limit` (по умолчанию 50, максимум 200), `offset`

```json
[
  {
    "id": "b0a7...",
    "first_seen_at": "...",
    "last_seen_at": "...",
    "parsed_profile": {
      "position_title": "Media Buyer",
      "total_experience_months": 18,
      "geo": "Москва",
      "salary_expectation": 1500,
      "skills": ["Facebook Ads", "Keitaro"],
      "text_blob": "..."
    },
    "crm_candidate_id": null,
    "review_status": "pending",
    "reviewed_at": null,
    "reviewed_by": null,
    "sources": [
      { "source": "hh", "external_id": "12345", "external_url": "https://hh.ru/resume/12345", "first_seen_at": "...", "last_seen_at": "..." }
    ],
    "scores": [
      { "search_template_id": "...", "score": 82, "tier": "high", "hard_filters_passed": true, "breakdown": {...}, "computed_at": "..." }
    ]
  }
]
```

`GET /external-candidates/{id}` — то же самое, но один кандидат (404, если не найден).

- `parsed_profile` — нормализованный профиль, одинаковый по форме независимо от
  источника (HH или Telegram) — это то, что должно попасть в CRM.
- `sources[]` — один кандидат может иметь несколько записей (пришёл и с HH, и из
  Telegram) — дедупликация уже сделана на нашей стороне.
- `scores[]` — по одной записи на каждый `search_template`, по которому кандидата
  оценивали (Telegram-кандидат оценивается только если у него указана вакансия,
  совпадающая с `crm_vacancy_id` какого-то шаблона).
- `crm_candidate_id` — зарезервировано на будущее (если понадобится, чтобы CRM
  сообщала нам свой ID), сейчас всегда `null`.

**Как CRM должна это использовать:** периодически (или по кнопке в UI) забирать
список с `review_status=pending`. Когда HR принимает решение — вызвать
`PATCH /external-candidates/{id}/review`, и только для `added` создавать
`Candidate`/`Application` в своей базе — как именно это делать дальше, решает CRM,
Recruitment Service не диктует.

### Триаж — `PATCH /external-candidates/{id}/review`

```
PATCH /external-candidates/{id}/review
{ "decision": "added", "reviewed_by": "hr@company.com" }   // или "skipped", или "pending" (чтобы отменить решение)
→ 200  (тот же объект ExternalCandidateOut, с обновлённым review_status/reviewed_at/reviewed_by)
```

`reviewed_by` необязателен — можно передать email/ID HR-пользователя для аудита, можно
не передавать.

---

## 4. Telegram-отклики — `/telegram/applications`

```
POST /telegram/applications
{
  "telegram_user_id": 123456789,
  "vacancy_ref": "vac-123",        // должен совпадать с crm_vacancy_id шаблона
  "candidate_text": "Опыт в Facebook Ads, iGaming, 8 месяцев",
  "resume_file_ref": null           // Telegram file_id или URL — не бинарный файл
}
→ 201
{ "telegram_application_id": "...", "external_candidate_id": "...", "scored_against_templates": 1 }
```

**Пока никто не вызывает этот эндпоинт** — существующий Telegram-бот (CGBot) ещё не
подключён к Recruitment Service (сознательное решение, отложено). Эндпоинт готов и
протестирован на будущее.

Важное отличие от HH: у Telegram-кандидата нет структурированного резюме — только
свободный текст. Поэтому все структурные критерии (`employment_type`, `salary_from`
и т.п.) для таких кандидатов автоматически не выполняются (`hard_filters_passed:
false`, если такой критерий стоит `required`), а работают только ключевые слова
(текст ищется по `candidate_text`). Это осознанное ограничение, не баг.

---

## 5. HH — статус подключения

| Метод | Путь | Auth | Описание |
|---|---|---|---|
| `GET` | `/providers/hh/status` | да | Подключён ли HH-аккаунт |
| `POST` | `/providers/hh/connect` | да | Вернуть `authorize_url` для OAuth |
| `GET` | `/providers/hh/callback?code=...` | **нет** | OAuth redirect-эндпоинт |

```
GET /providers/hh/status → 200
{ "connected": false, "account_id": null, "label": null, "status": null, "connected_at": null }
```

Flow подключения: CRM (от лица администратора/HR) вызывает `POST /connect`, получает
`authorize_url`, редиректит браузер администратора туда → HH спрашивает разрешение →
редиректит обратно на `HH_REDIRECT_URI` (наш `/providers/hh/callback`) → аккаунт
помечается подключённым.

`/callback` **не защищён `INTERNAL_SERVICE_TOKEN`** — это редирект из браузера, не
API-вызов от CRM. Технически сейчас требует отдельного решения по reachability (порт
`recruitment-api` не публикуется наружу) — см. отдельное обсуждение по nginx-проксированию.

HH-интеграция ещё не проверена вживую — приложение на модерации у HH.

---

## Рекомендуемый UI для CRM

```
Recruitment
├── 🔎 Поиск кандидатов
├── 📩 Отклики
├── 👤 Кандидаты
└── ⚙️ Настройки
```

Единый принцип: **всё новое (и результаты поиска, и входящие отклики) стартует как
`review_status=pending` и не становится «кандидатом», пока HR явно не нажмёт
«Добавить в кандидаты» или «Пропустить».** «🔎 Поиск кандидатов» и «📩 Отклики» — по
сути один и тот же пул pending-находок, просто с разным акцентом фильтров;
«👤 Кандидаты» — отдельный список только `review_status=added`.

### 🔎 Поиск кандидатов

- Шаблоны поиска: `GET /search-templates` — имя, привязанная вакансия, статус
  автопоиска, `last_run_at`/`last_success_at`/`last_error`.
- Форма шаблона:
  - Название, выбор вакансии CRM (её ID → `crm_vacancy_id`)
  - **Конструктор критериев** — HR выбирает из человеко-понятных полей (Должность,
    Опыт, Формат работы, Занятость, GEO, Язык, Зарплата, Статус поиска работы) +
    свободные теги (вертикаль/трафик-сорсы/технологии типа iGaming, Facebook,
    Keitaro, PWA). Каждый критерий — переключатель Приоритет
    (Обязательный/Желательный/Не учитывать) + слайдер веса (только для Желательного).
    UI сам маппит выбор в `key`/`value` из таблицы выше — HR никогда не видит
    сырые `key`.
  - Тумблер «Автопоиск» + селект интервала (15м/30м/1ч/2ч/6ч/12ч/24ч — ровно этот
    список, другие значения API отклонит).
  - Кнопка «Запустить поиск» → `POST /run`, дальше — поллинг статуса с индикатором
    queued/running/completed/failed и цифрами из `stats`.
- Результаты конкретного запуска/шаблона: `GET /external-candidates?search_template_id={id}&review_status=pending`
  — список найденного, ещё не разобранного HR. На каждой карточке — те же кнопки
  «Добавить в кандидаты» / «Пропустить», что и в «Откликах» (см. ниже) — это один и
  тот же `PATCH /review`.

### 📩 Отклики

- `GET /external-candidates?review_status=pending&source=hh` и `source=telegram` (и
  в будущем — HH negotiations, см. раздел «Чего пока нет»).
- Карточка: имя (если есть — только после раскрытия контактов HH, у Telegram — из
  текста заявки), позиция/текст отклика, GEO, бейдж тира (LOW/MEDIUM/HIGH/HOT,
  цветом), иконка источника, по клику — разбивка score (`breakdown`).
- Кандидатов с `hard_filters_passed: false` — либо не показывать по умолчанию, либо
  явно помечать «не прошёл обязательные критерии» (но всё равно давать решить HR
  вручную — это не запрет, а подсказка).
- Две кнопки на каждой карточке:
  - **«Добавить в кандидаты»** → `PATCH /external-candidates/{id}/review {"decision":"added"}`
    → дальше CRM создаёт свой `Candidate`/`Application` из `parsed_profile` + `sources`.
  - **«Пропустить»** → `{"decision":"skipped"}` — просто исчезает из pending, в
    «Кандидаты» не попадает.
- **Telegram** заработает после подключения CGBot к `/telegram/applications`
  (сейчас не подключён).

### 👤 Кандидаты

- `GET /external-candidates?review_status=added` — единая рабочая база: все, кого HR
  уже отобрала, независимо от источника и от того, из какого шаблона/отклика они
  пришли.
- Поиск/фильтрация — по имени, вакансии, тиру, источнику и т.п. (это уже поверх
  данных, которые отдаёт наш API — сама фильтрация может быть как на бэкенде CRM,
  так и клиентской, на усмотрение реализации).
- Дальнейший pipeline (этапы найма: скрининг/интервью/оффер/отказ) — **полностью
  в CRM**, Recruitment Service этого не хранит и не должен.
- Можно показывать `reviewed_by`/`reviewed_at` («кто и когда добавил») для аудита.

### ⚙️ Настройки

- Виджет статуса HH (`GET /providers/hh/status`) + кнопка «Подключить HH» → редирект
  на `authorize_url` из `POST /connect`.

---

## Чего в API пока нет / сознательно не будет

- **Опыт именно в конкретной вертикали/инструменте (не общий стаж)** — например
  «6+ месяцев именно в iGaming» или «3+ года именно с Meta Ads». Сейчас есть только
  два уровня: (а) ключевое слово встречается в тексте резюме где угодно — бинарно,
  без учёта длительности, и (б) `min_experience_months`/`experience_level` — это
  общий стаж кандидата, не по конкретной вертикали. Для точного варианта нужно
  парсить каждую запись `experience[]` резюме и суммировать длительность только
  совпадающих по описанию — не реализовано.
- **Именованные GEO-группы (Tier-1, LATAM и т.п.)** — у нас нет встроенного словаря
  таких групп. Через `|`-альтернативы (см. выше) можно передать явный список стран
  вручную, но сам список групп CRM должна поддерживать на своей стороне.
- **Размер команды / стаж управления командой** («3+ Media Buyer в подчинении»,
  «руководил командой 1+ год») — это глубоко в свободном тексте описания опыта,
  keyword-поиск такое надёжно не вытащит. Реалистично только с AI-разбором резюме
  (см. ниже) — не реализовано.
- **HH negotiations (входящие отклики на размещённые вакансии)** — **запланировано,
  ещё не реализовано.** Это отдельная от «поиска резюме» сущность HH API
  (`GET /negotiations`) — кандидат сам откликается на вакансию, размещённую вами на
  hh.ru, а не находится активным поиском. В отличие от поиска резюме, **не требует
  платного тарифа**. Когда будет реализовано — эти кандидаты попадут в тот же
  `/external-candidates` с `source: "hh"` (либо отдельным значением источника, если
  понадобится различать от поиска — уточним при реализации), пройдут тот же
  дедуп/scoring. Отдельного API для этого пока нет — не закладывайте в UI сейчас
  жёстко завязанную логику, ориентируйтесь на общий фильтр по источнику.
- **Push из Recruitment Service в CRM** — нет и не будет; модель только pull через
  этот API (см. «Принцип» в начале документа).
- **Auto-reply кандидатам через HH** — не реализовано (в брифе явно отложено),
  архитектурно возможно (см. исследование HH API — сообщения работают только внутри
  уже открытого отклика/приглашения, без массовых рассылок).
- **AI-скоринг** — отложено до стабилизации базового pipeline.
- **Валидация `crm_vacancy_id` / `geo_area_id` / `professional_role_id` по справочникам
  HH** — сейчас просто строки/числа, без проверки существования. Если понадобится
  UI с выбором региона/роли по названию — нужно отдельно реализовать обращение к
  `GET /areas` и `GET /dictionaries` HH.
