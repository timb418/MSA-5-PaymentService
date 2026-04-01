"""
Payment Service — Camunda Zeebe Workers
Task 4.2: Минимальный прототип саги оплаты

Workers (zeebe:type → handler):
  create-payment, debit-account, fraud-check, transfer-funds,
  update-payment-status, notify-client, cancel-payment,
  credit-account, notify-security

Демо-сценарии (запускаются автоматически после подключения):
  APPROVED      → счастливый путь → COMPLETED
  DENIED        → компенсация → REFUNDED
  FRAUD         → компенсация + уведомление СБ → REFUNDED
  MANUAL_REVIEW → пользовательская задача в Tasklist UI
"""

import asyncio
import logging
import os
import uuid

import grpc
from pyzeebe import ZeebeClient, ZeebeWorker, create_insecure_channel

# ── Логирование ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("payment-service")

# ── Конфигурация ───────────────────────────────────────────────────────────────
ZEEBE_ADDRESS = os.getenv("ZEEBE_ADDRESS", "zeebe:26500")

PROCESS_ID = "paymentProcess"

DEMO_SCENARIOS = [
    {
        "fraudScenario": "APPROVED",
        "amount": 100.00,
        "paymentId": f"pay-approved-{uuid.uuid4().hex[:6]}",
        "fromAccount": "ACC-1001",
        "toAccount":   "ACC-2001",
    },
    {
        "fraudScenario": "DENIED",
        "amount": 200.00,
        "paymentId": f"pay-denied-{uuid.uuid4().hex[:6]}",
        "fromAccount": "ACC-1002",
        "toAccount":   "ACC-2002",
    },
    {
        "fraudScenario": "FRAUD",
        "amount": 999.99,
        "paymentId": f"pay-fraud-{uuid.uuid4().hex[:6]}",
        "fromAccount": "ACC-1003",
        "toAccount":   "ACC-2003",
    },
    {
        "fraudScenario": "MANUAL_REVIEW",
        "amount": 50.00,
        "paymentId": f"pay-manual-{uuid.uuid4().hex[:6]}",
        "fromAccount": "ACC-1004",
        "toAccount":   "ACC-2004",
    },
]


# ── Ожидание готовности Zeebe ──────────────────────────────────────────────────
async def wait_for_zeebe(client: ZeebeClient, max_retries: int = 40, delay: float = 5.0):
    """
    Zeebe стартует ~30-60 сек. Используем topology() — лёгкий gRPC-запрос:
    - UNAVAILABLE → брокер ещё не готов, повторяем
    - успех → брокер готов к работе
    """
    logger.info("Ожидание Zeebe по адресу %s...", ZEEBE_ADDRESS)
    for attempt in range(1, max_retries + 1):
        try:
            await client.topology()
            logger.info("Zeebe готов (attempt %d)", attempt)
            return
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                logger.warning(
                    "Zeebe недоступен (attempt %d/%d), повтор через %.0f сек...",
                    attempt, max_retries, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.info("Zeebe готов (attempt %d, статус %s)", attempt, e.code())
                return
        except Exception as e:
            logger.warning(
                "Ошибка подключения (attempt %d/%d): %s",
                attempt, max_retries, str(e)[:120],
            )
            await asyncio.sleep(delay)
    raise RuntimeError(f"Zeebe недоступен после {max_retries} попыток")


# ── Запуск демо-экземпляров ────────────────────────────────────────────────────
async def start_demo_instances(client: ZeebeClient):
    """Запускает 4 экземпляра процесса с разными fraud-сценариями.
    Ждёт пока deploy-process задеплоит BPMN (retry до 12 раз × 10 сек)."""
    # Ждём деплоя BPMN — повторяем до успеха
    for wait_attempt in range(12):
        await asyncio.sleep(10)
        try:
            # пробный запуск: если процесс не найден — ещё ждём
            resp = await client.run_process(bpmn_process_id=PROCESS_ID, variables={"_probe": True})
            # успех — отменяем инстанс (он не нужен), начинаем демо
            try:
                await client.cancel_process_instance(resp.processInstanceKey)
            except Exception:
                pass
            break
        except Exception as exc:
            err = str(exc)
            if "was not found" in err or "NOT_FOUND" in err:
                logger.info("BPMN ещё не задеплоен, ждём... (попытка %d/12)", wait_attempt + 1)
            else:
                logger.warning("Неожиданная ошибка при проверке деплоя: %s", err[:120])
    else:
        logger.error("BPMN так и не появился за 120 секунд — запускаем без ожидания")

    logger.info("=" * 65)
    logger.info("  ЗАПУСК ДЕМО-ЭКЗЕМПЛЯРОВ (%d сценария)", len(DEMO_SCENARIOS))
    logger.info("=" * 65)

    for scenario in DEMO_SCENARIOS:
        try:
            resp = await client.run_process(
                bpmn_process_id=PROCESS_ID,
                variables=scenario,
            )
            logger.info(
                "  STARTED key=%-12s fraudScenario=%-14s paymentId=%s",
                getattr(resp, 'process_instance_key', getattr(resp, 'processInstanceKey', '?')),
                scenario["fraudScenario"],
                scenario["paymentId"],
            )
        except Exception as exc:
            logger.error(
                "  FAILED сценарий %s: %s",
                scenario["fraudScenario"], exc,
            )
        await asyncio.sleep(1)

    logger.info("=" * 65)
    logger.info("  Все экземпляры запущены.")
    logger.info("  Operate  → http://localhost:8081  (demo/demo)")
    logger.info("  Tasklist → http://localhost:8082  (demo/demo)")
    logger.info("=" * 65)


# ── Регистрация workers ────────────────────────────────────────────────────────
def register_workers(worker: ZeebeWorker) -> None:

    # ── 1. create-payment ──────────────────────────────────────────────────────
    @worker.task(task_type="create-payment")
    async def create_payment(
        paymentId: str = "",
        amount: float = 0.0,
        fromAccount: str = "UNKNOWN",
        **kwargs,
    ):
        pid = paymentId or f"pay-{uuid.uuid4().hex[:8]}"
        logger.info(
            "[create-payment]  paymentId=%s  amount=%.2f  from=%s  → INITIATED",
            pid, amount, fromAccount,
        )
        return {"paymentId": pid, "paymentStatus": "INITIATED"}

    # ── 2. debit-account ───────────────────────────────────────────────────────
    @worker.task(task_type="debit-account")
    async def debit_account(
        paymentId: str,
        amount: float = 0.0,
        fromAccount: str = "UNKNOWN",
        **kwargs,
    ):
        logger.info(
            "[debit-account]   paymentId=%s  amount=%.2f  from=%s  → FUNDS_RESERVED",
            paymentId, amount, fromAccount,
        )
        return {"paymentStatus": "FUNDS_RESERVED"}

    # ── 3. fraud-check ─────────────────────────────────────────────────────────
    @worker.task(task_type="fraud-check")
    async def fraud_check(
        paymentId: str,
        fraudScenario: str = "APPROVED",
        **kwargs,
    ):
        """
        Эмулирует антифрод-проверку. fraudScenario управляет результатом:
          APPROVED      → APPROVED,       isFraud=False
          DENIED        → DENIED,         isFraud=False  (отказ без мошенничества)
          FRAUD         → DENIED,         isFraud=True   (мошенничество → СБ)
          MANUAL_REVIEW → MANUAL_REVIEW,  isFraud=False  (ручная проверка)
        """
        mapping = {
            "APPROVED":      ("APPROVED",      False),
            "DENIED":        ("DENIED",        False),
            "FRAUD":         ("DENIED",        True),
            "MANUAL_REVIEW": ("MANUAL_REVIEW", False),
        }
        fraud_result, is_fraud = mapping.get(fraudScenario, ("APPROVED", False))
        logger.info(
            "[fraud-check]     paymentId=%s  scenario=%-14s → fraudResult=%s  isFraud=%s",
            paymentId, fraudScenario, fraud_result, is_fraud,
        )
        return {"fraudResult": fraud_result, "isFraud": is_fraud}

    # ── 4. transfer-funds (PIVOT POINT) ────────────────────────────────────────
    @worker.task(task_type="transfer-funds")
    async def transfer_funds(
        paymentId: str,
        amount: float = 0.0,
        toAccount: str = "UNKNOWN",
        **kwargs,
    ):
        logger.info(
            "[transfer-funds]  paymentId=%s  amount=%.2f  to=%s  → TRANSFER_IN_PROGRESS  ★ PIVOT",
            paymentId, amount, toAccount,
        )
        return {"paymentStatus": "TRANSFER_IN_PROGRESS"}

    # ── 5. update-payment-status (dual: success + failure) ────────────────────
    @worker.task(task_type="update-payment-status")
    async def update_payment_status(
        paymentId: str,
        paymentStatus: str = "",
        **kwargs,
    ):
        """
        Используется на двух путях:
          TRANSFER_IN_PROGRESS → COMPLETED
          REFUND_IN_PROGRESS   → REFUNDED
        """
        new_status = {
            "TRANSFER_IN_PROGRESS": "COMPLETED",
            "REFUND_IN_PROGRESS":   "REFUNDED",
        }.get(paymentStatus, paymentStatus)

        logger.info(
            "[update-status]   paymentId=%s  %s → %s",
            paymentId, paymentStatus, new_status,
        )
        return {"paymentStatus": new_status}

    # ── 6. notify-client (dual: success + failure) ────────────────────────────
    @worker.task(task_type="notify-client")
    async def notify_client(
        paymentId: str,
        paymentStatus: str = "",
        **kwargs,
    ):
        """
        Используется на двух путях — определяем по paymentStatus.
        """
        if paymentStatus == "COMPLETED":
            logger.info(
                "[notify-client]   SUCCESS ✓  paymentId=%s  Клиент уведомлён об успешном платеже.",
                paymentId,
            )
        elif paymentStatus == "REFUNDED":
            logger.info(
                "[notify-client]   FAILURE ✗  paymentId=%s  Клиент уведомлён об отклонении/возврате.",
                paymentId,
            )
        else:
            logger.warning("[notify-client]   paymentId=%s  неизвестный статус: %s", paymentId, paymentStatus)
        return {}

    # ── 7. credit-account (компенсация DEBIT_ACCOUNT) ─────────────────────────
    @worker.task(task_type="credit-account")
    async def credit_account(
        paymentId: str,
        amount: float = 0.0,
        fromAccount: str = "UNKNOWN",
        **kwargs,
    ):
        logger.info(
            "[credit-account]  paymentId=%s  amount=%.2f  to=%s  → REFUND_IN_PROGRESS  (компенсация)",
            paymentId, amount, fromAccount,
        )
        return {"paymentStatus": "REFUND_IN_PROGRESS"}

    # ── 8. cancel-payment (компенсация CREATE_PAYMENT) ────────────────────────
    @worker.task(task_type="cancel-payment")
    async def cancel_payment(paymentId: str, **kwargs):
        logger.info(
            "[cancel-payment]  paymentId=%s  Запись платежа отменена в БД.  (компенсация)",
            paymentId,
        )
        return {}

    # ── 9. notify-security (только при isFraud=true) ──────────────────────────
    @worker.task(task_type="notify-security")
    async def notify_security(
        paymentId: str,
        fraudResult: str = "",
        fromAccount: str = "UNKNOWN",
        **kwargs,
    ):
        logger.info(
            "[notify-security] FRAUD ALERT ⚠  paymentId=%s  account=%s  fraudResult=%s  → СБ уведомлена!",
            paymentId, fromAccount, fraudResult,
        )
        return {}


# ── Точка входа ────────────────────────────────────────────────────────────────
async def run():
    logger.info("Payment Service запускается. Zeebe: %s", ZEEBE_ADDRESS)

    channel = create_insecure_channel(grpc_address=ZEEBE_ADDRESS)
    client = ZeebeClient(channel)
    worker = ZeebeWorker(channel)

    register_workers(worker)
    logger.info(
        "Workers зарегистрированы: create-payment, debit-account, fraud-check, "
        "transfer-funds, update-payment-status, notify-client, "
        "cancel-payment, credit-account, notify-security"
    )

    await wait_for_zeebe(client)

    await asyncio.gather(
        worker.work(),
        start_demo_instances(client),
    )


if __name__ == "__main__":
    asyncio.run(run())
