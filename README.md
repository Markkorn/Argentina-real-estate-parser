# Argentina Rental Parser

Небольшой шаблон парсера для сбора объявлений об аренде жилья в Аргентине. Он рассчитан на HTML‑страницы с карточками объявлений и использует CSS‑селекторы, которые задаются в конфиге.

## Что умеет
- Загружает страницы по пагинации.
- Парсит карточки объявлений через CSS‑селекторы.
- Сохраняет результат в `JSONL` (одна строка — одно объявление).

> ⚠️ Убедитесь, что вы соблюдаете правила сайта, его `robots.txt` и условия использования.

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Если не хотите ставить зависимости, парсер может работать на стандартной библиотеке, но поддержка CSS‑селекторов будет ограничена (классы и `tag.class`).

## Веб-интерфейс для генерации конфига

Чтобы быстро собрать конфигурацию, откройте HTML-интерфейс:

```bash
python -m http.server 8000 --directory web
```

Далее перейдите на `http://localhost:8000`, заполните параметры и скачайте готовый JSON.

## Рекомендуемый вариант при блокировке PyPI

Если доступ к PyPI блокируется прокси, самый простой вариант — запускать локальный прогон с `config/local_config.json`. Он не требует установки зависимостей и подтверждает, что парсер работает на примере HTML‑файла. После этого уже можно настраивать прокси или внутренний индекс Python‑пакетов для реальных сайтов.

Обновите `config/example_config.json` под сайт, который хотите парсить:

```json
{
  "base_url": "https://example.com/rentals",
  "page_param": "page",
  "start_page": 1,
  "end_page": 3,
  "local_html_path": null,
  "listing_type": "rent",
  "listings_selector": ".listing-card",
  "title_selector": ".listing-card__title",
  "price_selector": ".listing-card__price",
  "location_selector": ".listing-card__location",
  "url_selector": ".listing-card__link",
  "min_price": 200000,
  "max_price": 500000,
  "title_keywords_include": ["departamento", "monoambiente"],
  "location_keywords_include": ["palermo", "recoleta"]
}
```

Запуск:

```bash
python src/rentals_parser.py --config config/example_config.json
```

Вывод будет сохранён в `output/listings.jsonl`.

## Быстрый локальный прогон

Чтобы убедиться, что парсер работает без обращения к реальному сайту, используйте локальный HTML:

```bash
python src/rentals_parser.py --config config/local_config.json
```

Результат появится в `output/local_listings.jsonl`. В `config/local_config.json` настроены фильтры, чтобы показать работу критериев (цена, ключевые слова).

## Настройка селекторов

1. Откройте страницу с объявлениями.
2. Посмотрите HTML‑структуру карточек (DevTools).
3. Вставьте CSS‑селекторы в конфиг, чтобы они указывали на нужные элементы.

## Как искать аренду, покупку и фильтровать результаты

1. Для аренды используйте `"listing_type": "rent"` и подходящий `base_url` сайта.
2. Для покупки жилья поставьте `"listing_type": "sale"` (или любой удобный для вас ярлык) и укажите другой `base_url`/селекторы, если страницы отличаются.
3. Фильтры:
   - `min_price` / `max_price` — числовой диапазон цены (все цифры из строки цены будут объединены).
   - `title_keywords_include` — ключевые слова, которые должны встречаться в заголовке.
   - `location_keywords_include` — ключевые слова, которые должны встречаться в локации.

## Формат результата

```json
{"title": "Departamento en Palermo", "price": "ARS 350000", "location": "Palermo, CABA", "url": "https://..."}
```
