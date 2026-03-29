# Таблица переходов State Machine — OrchestrPay Payment

## Состояния платёжной операции

| Состояние | Описание | Тип |
|---|---|---|
| `INITIATED` | Платёж создан, запись в БД инициализирована | Промежуточное |
| `FUNDS_RESERVED` | Средства зарезервированы (списаны со счёта плательщика) | Промежуточное |
| `FRAUD_CHECK_IN_PROGRESS` | Запрос в антифрод-сервис отправлен, ожидается ответ | Промежуточное (ожидание) |
| `MANUAL_REVIEW_PENDING` | Ожидание решения оператора при ручной антифрод-проверке (≤ 20 мин) | Промежуточное (ожидание) |
| `TRANSFER_IN_PROGRESS` | Перевод средств контрагенту выполняется (после pivot-точки) | Промежуточное |
| `REFUND_IN_PROGRESS` | Возврат средств на счёт плательщика выполняется | Промежуточное |
| `COMPLETED` | Платёж успешно завершён, средства переведены контрагенту | **Финальное** |
| `REFUNDED` | Средства возвращены плательщику, платёж отменён | **Финальное** |
| `FAILED` | Платёж завершился ошибкой до резервирования средств | **Финальное** |

## Таблица переходов

| Исходное состояние | Переходное состояние | Событие |
|---|---|---|
| — | `INITIATED` | `PAYMENT_INITIATED` — пользователь инициировал платёж |
| `INITIATED` | `FUNDS_RESERVED` | `DEBIT_SUCCEEDED` — средства успешно зарезервированы |
| `INITIATED` | `FAILED` | `DEBIT_FAILED` — ошибка при попытке списания средств |
| `FUNDS_RESERVED` | `FRAUD_CHECK_IN_PROGRESS` | `FRAUD_CHECK_STARTED` — запрос в антифрод-сервис отправлен |
| `FRAUD_CHECK_IN_PROGRESS` | `FRAUD_CHECK_IN_PROGRESS` | `FRAUD_CHECK_TIMEOUT` — тайм-аут ответа, запрос повторяется (retry) |
| `FRAUD_CHECK_IN_PROGRESS` | `TRANSFER_IN_PROGRESS` | `FRAUD_CHECK_APPROVED` — антифрод разрешил проведение операции |
| `FRAUD_CHECK_IN_PROGRESS` | `MANUAL_REVIEW_PENDING` | `FRAUD_CHECK_MANUAL_REVIEW_REQUIRED` — антифрод запросил ручную проверку |
| `FRAUD_CHECK_IN_PROGRESS` | `REFUND_IN_PROGRESS` | `FRAUD_CHECK_REJECTED` — антифрод запретил проведение операции |
| `MANUAL_REVIEW_PENDING` | `TRANSFER_IN_PROGRESS` | `MANUAL_REVIEW_APPROVED` — оператор одобрил операцию |
| `MANUAL_REVIEW_PENDING` | `REFUND_IN_PROGRESS` | `MANUAL_REVIEW_REJECTED` — оператор отклонил операцию |
| `MANUAL_REVIEW_PENDING` | `TRANSFER_IN_PROGRESS` | `CUT_OFF_TIMER_EXPIRED` — истекло 20 мин ожидания, операция авто-одобрена |
| `TRANSFER_IN_PROGRESS` | `COMPLETED` | `TRANSFER_SUCCEEDED` — перевод средств контрагенту выполнен успешно |
| `REFUND_IN_PROGRESS` | `REFUNDED` | `REFUND_SUCCEEDED` — возврат средств плательщику выполнен успешно |
| `REFUND_IN_PROGRESS` | `REFUND_IN_PROGRESS` | `REFUND_FAILED` — ошибка возврата, повтор (retry) |

## Сценарии и маршруты по состояниям

### Успешный платёж
```
— → INITIATED → FUNDS_RESERVED → FRAUD_CHECK_IN_PROGRESS → TRANSFER_IN_PROGRESS → COMPLETED
```

### Ручная проверка → одобрение
```
... → FRAUD_CHECK_IN_PROGRESS → MANUAL_REVIEW_PENDING → TRANSFER_IN_PROGRESS → COMPLETED
```

### Ручная проверка → cut-off таймер (авто-одобрение)
```
... → MANUAL_REVIEW_PENDING --[20 мин]--> TRANSFER_IN_PROGRESS → COMPLETED
```

### Ручная проверка → отклонение
```
... → MANUAL_REVIEW_PENDING → REFUND_IN_PROGRESS → REFUNDED
```

### Отклонение антифродом
```
... → FRAUD_CHECK_IN_PROGRESS → REFUND_IN_PROGRESS → REFUNDED
```

### Ошибка при списании (до резервирования)
```
— → INITIATED → FAILED
```

## Пояснения

- **Состояния ожидания** (`FRAUD_CHECK_IN_PROGRESS`, `MANUAL_REVIEW_PENDING`) — платёж находится в них до получения внешнего ответа; именно в них важно фиксировать состояние в State Machine для корректного восстановления после сбоев.
- **Self-loop** у `FRAUD_CHECK_IN_PROGRESS` и `REFUND_IN_PROGRESS` — отражает retry-механизм: состояние не меняется, повторяется тот же запрос.
- **Pivot-точка** — переход в `TRANSFER_IN_PROGRESS`; после него компенсационные транзакции не применяются, перевод должен завершиться успехом.
- **Cut-off таймер** — событие `CUT_OFF_TIMER_EXPIRED` инициируется Camunda по истечении 20-минутного таймера; транзакция считается разрешённой по умолчанию.
