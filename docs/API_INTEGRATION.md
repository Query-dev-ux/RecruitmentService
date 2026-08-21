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

```
GET /external-candidates?search_template_id={id}&min_score=55&source=hh&limit=50&offset=0
```

Параметры (все опциональны):
- `source` — `hh` | `telegram`
- `search_template_id` — только кандидаты, оценённые по этому шаблону
- `min_score` — только с score ≥ N (0–100)
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
список, и для новых/подходящих кандидатов создавать `Candidate`/`Application` в своей
базе — как именно это делать, решает CRM, Recruitment Service не диктует.

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

Раздел в навигации CRM, примерно так, как было в исходном ТЗ:

```
Recruitment
├── Поисковые шаблоны
├── Кандидаты
├── Отклики (Telegram — после подключения бота)
└── Настройки
```

### Поисковые шаблоны

- Список: `GET /search-templates` — имя, привязанная вакансия, статус автопоиска,
  `last_run_at`/`last_success_at`/`last_error`.
- Форма создания/редактирования:
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

### Кандидаты

- `GET /external-candidates` с фильтрами по вакансии/шаблону, источнику, минимальному
  score.
- Карточка: имя (если есть — только после раскрытия контактов HH), позиция, GEO,
  бейдж тира (LOW/MEDIUM/HIGH/HOT, цветом), иконки источников (HH/Telegram), по клику
  — разбивка score (`breakdown`) для прозрачности HR.
- Кандидатов с `hard_filters_passed: false` — либо не показывать по умолчанию, либо
  явно помечать «не прошёл обязательные критерии».
- Действие «Добавить в CRM» — здесь начинается зона ответственности CRM: создание
  своего `Candidate`/`Application` из данных `parsed_profile` + `sources`. Recruitment
  Service в этот момент уже не участвует.

### Отклики (Telegram + HH negotiations)

Можно не делать отдельным экраном — просто фильтр по источнику (`telegram`, в будущем
и `hh-negotiation`) на экране «Кандидаты».

- **Telegram** — актуально после подключения CGBot к `/telegram/applications`
  (сейчас не подключён).
- **HH negotiations** (входящие отклики на вакансии, размещённые на hh.ru, в отличие
  от активного поиска по базе резюме) — **API-эндпоинт пока не реализован**, но
  архитектурно запланирован как ещё один источник в тот же pipeline
  (дедуп/scoring/`external-candidates`). См. раздел ниже.

### Настройки

- Виджет статуса HH (`GET /providers/hh/status`) + кнопка «Подключить HH» → редирект
  на `authorize_url` из `POST /connect`.

---

## Чего в API пока нет / сознательно не будет

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
