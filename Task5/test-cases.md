# Task 5. Тест-кейсы: интеграционные и end-to-end тесты

## Контекст

Тесты покрывают платёжный процесс OrchestrPay, реализованный через Saga-оркестрацию на Camunda Zeebe.
Сервисы: **Payment Service** (Python-воркеры), **FraudCheck Service** (эмулируется воркером `fraud-check`), **Notification Service** (воркеры `notify-client`, `notify-security`), **Camunda Zeebe** (BPMN-движок).

---

## Таблица тест-кейсов

| Название | Тип | Компоненты | Предусловия |
|---|---|---|---|
| **HappyPath_FraudApproved** | E2E | Payment Service, FraudCheck Service, Notification Service, Zeebe | Zeebe запущен и доступен; BPMN-процесс задеплоен; у пользователя достаточно средств на счёте; `fraudScenario = APPROVED` |
| **FraudDenied_CompensationChain** | E2E | Payment Service, FraudCheck Service, Notification Service, Zeebe | Zeebe запущен; BPMN задеплоен; `fraudScenario = DENIED`; деньги успешно зарезервированы (DEBIT прошёл) |
| **FraudDetected_SecurityNotification** | E2E | Payment Service, FraudCheck Service, Notification Service, Zeebe | Zeebe запущен; BPMN задеплоен; `fraudScenario = FRAUD` (isFraud = true); инициирована компенсационная цепочка |
| **ManualReview_OperatorApproves** | E2E | Payment Service, FraudCheck Service, Notification Service, Zeebe, Tasklist UI | Zeebe запущен; BPMN задеплоен; `fraudScenario = MANUAL_REVIEW`; Tasklist UI доступен на порту 8082; оператор готов принять решение в течение 20 минут |
| **ManualReview_OperatorRejects** | E2E | Payment Service, FraudCheck Service, Notification Service, Zeebe, Tasklist UI | Zeebe запущен; BPMN задеплоен; `fraudScenario = MANUAL_REVIEW`; Tasklist UI доступен; оператор отклоняет транзакцию |
| **ManualReview_CutOffTimer** | E2E | Payment Service, FraudCheck Service, Notification Service, Zeebe | Zeebe запущен; BPMN задеплоен; `fraudScenario = MANUAL_REVIEW`; оператор не выполняет никаких действий в течение 20 минут (PT20M); граничный таймер настроен в BPMN |
| **CreatePayment_Worker** | Интеграционный | Payment Service (воркер `create-payment`), Zeebe | Zeebe запущен; воркер `create-payment` зарегистрирован и опрашивает очередь; в переменных процесса переданы `paymentId`, `userId`, `amount` |
| **DebitAccount_Worker** | Интеграционный | Payment Service (воркер `debit-account`), Zeebe | Zeebe запущен; предшествующий шаг CREATE_PAYMENT завершён; `paymentStatus = INITIATED` |
| **FraudCheck_Worker_AllResults** | Интеграционный | FraudCheck Service (воркер `fraud-check`), Zeebe | Zeebe запущен; `paymentStatus = FUNDS_RESERVED`; тест запускается трижды с `fraudScenario` = APPROVED, DENIED, MANUAL_REVIEW |
| **TransferFunds_PivotPoint** | Интеграционный | Payment Service (воркер `transfer-funds`), Zeebe | Zeebe запущен; fraud-check вернул APPROVED или решение ручной проверки = APPROVED; `paymentStatus = FRAUD_CHECK_IN_PROGRESS → pivot`; компенсационный путь недоступен после этого шага |
| **UpdatePaymentStatus_Worker** | Интеграционный | Payment Service (воркер `update-payment-status`), Zeebe | Zeebe запущен; процесс находится на шаге UPDATE_PAYMENT_STATUS; переменная `paymentStatus` содержит одно из допустимых значений (TRANSFER_IN_PROGRESS или REFUND_IN_PROGRESS) |
| **NotifyClient_Worker_BothPaths** | Интеграционный | Notification Service (воркер `notify-client`), Zeebe | Zeebe запущен; процесс достиг шага NOTIFY_CLIENT; тест запускается дважды: с `paymentStatus = COMPLETED` и с `paymentStatus = REFUNDED` |
| **CreditAccount_Compensation** | Интеграционный | Payment Service (воркер `credit-account`), Zeebe | Zeebe запущен; DEBIT_ACCOUNT был выполнен ранее (`paymentStatus = FUNDS_RESERVED`); инициирован компенсационный поток (fraud denied или ошибка) |
| **CancelPayment_Compensation** | Интеграционный | Payment Service (воркер `cancel-payment`), Zeebe | Zeebe запущен; CREATE_PAYMENT был выполнен ранее; CREDIT_ACCOUNT завершён; компенсационная цепочка активна |
| **NotifySecurity_OnFraudOnly** | Интеграционный | Notification Service (воркер `notify-security`), Zeebe | Zeebe запущен; два прохода: (1) `isFraud = true` — воркер должен быть вызван; (2) `isFraud = false` — воркер не должен вызываться |
| **ZeebeWorkerRegistration** | Интеграционный | Payment Service (все 9 воркеров), Zeebe | Zeebe запущен и доступен по gRPC (порт 26500); контейнер `payment-service` запускается; топология Zeebe содержит хотя бы один брокер |
| **ProcessDeployment** | Интеграционный | deploy-process (Dockerfile + BPMN), Zeebe | Zeebe запущен; контейнер `deploy-process` запускается; файл `process.bpmn` присутствует в образе; retry-механизм (12 × 10 сек) настроен |
| **BoundaryTimer_ManualReview** | Интеграционный | Zeebe (BPMN-движок), Payment Service | Zeebe запущен; процесс ожидает на шаге WAIT_MANUAL_REVIEW; граничный таймер PT20M настроен в BPMN; тест использует ускоренное время или Zeebe clock API |
| **StateTransition_AllStates** | Интеграционный | Payment Service, FraudCheck Service, Zeebe | Zeebe запущен; BPMN задеплоен; доступны сценарии для достижения всех 9 состояний: INITIATED, FUNDS_RESERVED, FRAUD_CHECK_IN_PROGRESS, MANUAL_REVIEW_PENDING, TRANSFER_IN_PROGRESS, REFUND_IN_PROGRESS, COMPLETED, REFUNDED, FAILED |
| **VariablePropagation** | Интеграционный | Payment Service (все воркеры), Zeebe | Zeebe запущен; процесс инициирован с переменными `paymentId`, `userId`, `amount`, `fraudScenario`; каждый воркер корректно читает и обновляет переменные перед передачей следующему шагу |

---

## Легенда типов

| Тип | Описание |
|---|---|
| **E2E** | Полный сквозной сценарий от инициации платежа до конечного состояния процесса (COMPLETED, REFUNDED). Проверяет взаимодействие всех компонентов. |
| **Интеграционный** | Проверка отдельного воркера или подсистемы (деплой, таймер, регистрация) в связке с Zeebe. Входные и выходные переменные задаются явно. |
