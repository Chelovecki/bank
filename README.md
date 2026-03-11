# Payment Service

Тестовое задание: сервис платежей по заказам с поддержкой наличных и эквайринга.

## Что реализовано

- Модели `Order` и `Payment` в PostgreSQL (SQLAlchemy + Alembic).
- Статусы заказа: `UNPAID`, `PARTIALLY_PAID`, `PAID`.
- Типы платежей: `CASH`, `ACQUIRING`.
- Операции платежа:
  - создание (`deposit`) через `POST /orders/{order_id}/payments`;
  - возврат (`refund`) через `POST /payments/{payment_id}/refund`.
- Ограничение: сумма активных платежей (`PENDING` + `COMPLETED`) по заказу не превышает сумму заказа.
- Интеграция с внешним API банка:
  - `acquiring_start` при создании эквайрингового платежа;
  - `acquiring_check` для синхронизации состояния.
- Согласование состояний банка и приложения:
  - `POST /payments/{payment_id}/sync`;
  - `POST /orders/{order_id}/payments/sync`.

## Архитектура API банка

- `src/api/bank_client.py`:
  - `BankClient.acquiring_start(order_id, amount) -> bank_payment_id`;
  - `BankClient.acquiring_check(bank_payment_id) -> BankCheckResult`.
- Ошибки внешней системы разделены на:
  - временные (`BankTemporaryError`);
  - постоянные (`BankPermanentError`);
  - доменные (`BankPaymentNotFoundError`).
- Во внутренних сервисах (`src/api/payment/services.py`) эти ошибки обрабатываются как ошибки внешней системы, а в REST-слое преобразуются в корректные HTTP-ответы.

## REST ручки

- `GET /orders` - список заказов.
- `GET /orders/{order_id}` - один заказ.
- `GET /orders/{order_id}/payments` - платежи заказа.
- `POST /orders/{order_id}/payments` - создать платеж.
- `POST /orders/{order_id}/payments/sync` - синхронизировать эквайринг-платежи заказа с банком.
- `GET /payments/{payment_id}` - один платеж.
- `POST /payments/{payment_id}/refund` - возврат платежа.
- `POST /payments/{payment_id}/sync` - синхронизировать платеж с банком.

## Схема БД

### `orders`

- `id` `int` PK
- `amount` `numeric(10,2)` not null
- `payment_status` `varchar` not null
- `created_at` `timestamptz` not null

### `payments`

- `id` `int` PK
- `order_id` `int` FK -> `orders.id` (`ON DELETE CASCADE`)
- `amount` `numeric(10,2)` not null, check `amount > 0`
- `type` `varchar` not null (`CASH`/`ACQUIRING`)
- `status` `varchar` not null (`PENDING`/`COMPLETED`/`REFUNDED`)
- `bank_payment_id` `varchar(100)` null
- `bank_status` `varchar(50)` null
- `bank_checked_at` `timestamptz` null
- `bank_paid_at` `timestamptz` null
- `created_at` `timestamptz` not null

Связь: `orders 1 -> N payments`.

## Тесты

Локально:

- `uv sync --dev`
- `uv run pytest -q`

В Docker:

- `docker compose -f docker/docker-compose.yml -f docker/docker-compose.tests.yml run --rm tests`
