# NeoMarket — B2C Storefront

Команда «алкобаг и точка» (Forge). Модуль: **B2C** (витрина покупателя).
Отдельный сервис, не зависит от B2B-кода — данные каталога и резерва берутся из B2B по HTTP.

## Реализованные milestone-контракты (для зачёта)

| Контракт | Эндпоинт(ы) | Файлы |
|----------|-------------|-------|
| US-CAT-01 — каталог с фильтрами и фасетами | `GET /api/v1/products`, `GET /api/v1/catalog/facets` | `routes/catalog.py` |
| US-CAT-03 — карточка товара покупателя | `GET /api/v1/products/{id}` | `routes/catalog.py` |
| US-CART-03 — корзина | `GET/DELETE /api/v1/cart`, `POST /api/v1/cart/items`, `PUT/DELETE /api/v1/cart/items/{item_id}`, merge при логине | `routes/cart.py`, `services/cart_service.py` |
| US-ORD-01 — checkout (тело `{idempotency_key, items, delivery_address}`) | `POST /api/v1/orders` | `routes/orders.py`, `services/order_service.py` |
| US-ORD-03 — отмена заказа | `POST /api/v1/orders/{id}/cancel` | `routes/orders.py`, `services/order_service.py` |

Вспомогательное (нужно для checkout): минимальные `auth/register|login`, `addresses`, `payment-methods`.

## Стек

FastAPI, SQLAlchemy 2, PostgreSQL (тесты — SQLite in-memory), PyJWT (HS256), httpx, Docker.
Тесты — pytest. CI — GitHub Actions (`.github/workflows/ci.yml`).

## Архитектура

- **B2C не хранит товары.** Каталог, остатки SKU и reserve/unreserve — в B2B-сервисе.
  Вся интеграция инкапсулирована в `src/b2b_client.py` (`B2BClient` protocol + `HttpB2BClient`).
  В тестах клиент подменяется `FakeB2BClient` через `app.dependency_overrides` — сервис
  проверяется полностью офлайн, без живого B2B.
- Своя БД B2C: покупатели, адреса, платёжные методы, корзина, заказы, ключи идемпотентности.
- Чекаут идемпотентен по заголовку `Idempotency-Key` (повтор с тем же телом → тот же заказ;
  с другим телом → 409).

## Запуск

```bash
docker compose up          # API: http://localhost:8000/docs
```

Без Docker:

```bash
pip install -r requirements-dev.txt
cp .env.example .env       # выставить JWT_SECRET, B2B_BASE_URL, B2B_SERVICE_KEY
uvicorn src.main:app --reload
```

## Тесты

```bash
pip install -r requirements-dev.txt
PYTHONPATH=. pytest -v
```

## Соглашения (type-unification канона)

ID — UUID. Деньги — integer в копейках. Поля — snake_case. Пагинация — `{items, total_count, limit, offset}`.
Ошибки — плоский `{"code": "...", "message": "..."}`; валидация → `400 INVALID_REQUEST`.
JWT Bearer HS256, `buyer_id` только из claim `sub`, никогда из тела. Сервис-сервис к B2B — заголовок `X-Service-Key`.

## Канон vs протокол — ВАЖНО

DoD каждого B2C-квеста привязан к **канон-flow** (`flows/b2c-*-flows.md`), а пер-доменные
OpenAPI (`b2c/catalog/openapi.yaml`, `b2c/orders/openapi.yaml`) **ещё не опубликованы** —
есть только сводный `b2c/openapi.yaml`. Поэтому governing-источник = канон-flow, и пути/контракты
сделаны по нему:
- CAT-01: `GET /api/v1/products` + `GET /api/v1/catalog/facets`, sort-enum канона
  (`rating, popularity, price_asc, price_desc, date_desc, discount_desc`).
- ORD-01: тело `{idempotency_key, items[{sku_id, quantity}], delivery_address?}`,
  ответ `{id, status, items[{product_title, sku_name, unit_price, line_total, …}], total_amount, …}`.

**Все 5 milestone сверены с DoD на платформе** — пути, контракты и точные имена pytest-сценариев
внесены по каждому квесту (см. таблицу ниже).

## ⚠️ Перед сдачей каждого контракта

1. Каждый контракт — **отдельная ветка и отдельный PR** (см. ниже).
2. Открыть страницу квеста и **сверить точные имена pytest-тестов из DoD**. Для CAT-01 и ORD-01
   имена уже внесены точно; для CAT-03, CART-03, ORD-03 — пока кандидаты, привести к DoD.
3. В описании PR — ADR (см. `ADR.md`) + лог pytest (или зелёный CI).

### Точные имена pytest-тестов из DoD (внесены)

| Контракт | Обязательные сценарии DoD |
|----------|---------------------------|
| US-CAT-01 | `catalog_returns_filtered_sorted_products`, `facets_return_counts_per_filter_value`, `invalid_sort_returns_400`, `b2b_unavailable_returns_502` |
| US-CAT-03 | `product_card_returns_full_data_with_skus`, `cost_price_absent_in_response`, `blocked_product_returns_404` |
| US-CART-03 | `add_sku_increments_quantity_if_already_in_cart`, `get_cart_enriched_with_b2b_data`, `unavailable_sku_shown_with_reason`, `guest_cart_merged_on_login` |
| US-ORD-01 | `checkout_creates_paid_order_with_fixed_prices`, `partial_reserve_failure_returns_409`, `idempotency_returns_existing_order`, `b2b_unavailable_returns_503` |
| US-ORD-03 | `cancel_paid_order_transitions_to_cancelled`, `unreserve_failure_transitions_to_cancel_pending`, `cancel_assembling_order_returns_409`, `other_user_order_returns_404` |

> В каждом квесте DoD требует «лог pytest по этим именам» либо зелёный GitHub Actions. В файлах
> `tests/` функции названы `test_<имя_сценария>` — это и есть требуемые имена.

### Ветки под PR

```
us-cat-01-catalog-filters     -> tests/test_cat_01_catalog.py + routes/catalog.py (list)
us-cat-03-view-product-card   -> tests/test_cat_03_product_card.py + routes/catalog.py (detail)
us-cart-03-cart               -> tests/test_cart_03_cart.py + routes/cart.py + services/cart_service.py
us-ord-01-checkout            -> tests/test_ord_01_checkout.py + routes/orders.py + services/order_service.py
us-ord-03-cancel-order        -> tests/test_ord_03_cancel_order.py + routes/orders.py + services/order_service.py
```

Каркас (config/database/errors/auth/b2b_client/models/schemas/main + infra) заливается первым PR
или в ветку первого контракта, чтобы остальные на него встали.
