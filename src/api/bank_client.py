from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from httpx import AsyncClient, HTTPError, TimeoutException
from pydantic import BaseModel, ConfigDict

from src.api.bank_client_exceptions import (
    BankPaymentNotFoundError,
    BankPermanentError,
    BankTemporaryError,
)


class BankPaymentState(StrEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"


class BankCheckResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bank_payment_id: str
    amount: Decimal
    status: BankPaymentState
    paid_at: datetime | None = None


class BankClientProtocol(Protocol):
    async def acquiring_start(self, order_id: int, amount: Decimal) -> str: ...

    async def acquiring_check(self, bank_payment_id: str) -> BankCheckResult: ...


class BankClient:
    def __init__(self, base_url: str, timeout_seconds: float, retries: int = 2):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.retries = max(1, retries)

    async def acquiring_start(self, order_id: int, amount: Decimal) -> str:
        payload = {"order_id": order_id, "amount": str(amount)}
        data = await self._post_json("acquiring_start", payload)
        bank_payment_id = data.get("bank_payment_id") or data.get("id")

        if not bank_payment_id:
            error_text = data.get("error") or "bank did not return payment id"
            raise BankPermanentError(str(error_text))

        return str(bank_payment_id)

    async def acquiring_check(self, bank_payment_id: str) -> BankCheckResult:
        payload = {"bank_payment_id": bank_payment_id}
        data = await self._post_json("acquiring_check", payload)

        if data.get("error") == "payment not found":
            raise BankPaymentNotFoundError(bank_payment_id)

        status = self._normalize_status(str(data.get("status")))

        try:
            paid_at_raw = data.get("paid_at")
            paid_at = datetime.fromisoformat(paid_at_raw) if paid_at_raw else None
            if paid_at and paid_at.tzinfo is None:
                paid_at = paid_at.replace(tzinfo=timezone.utc)
            amount = Decimal(str(data.get("amount")))
        except (TypeError, ValueError) as exc:
            raise BankPermanentError(
                f"invalid bank acquiring_check payload: {exc}"
            ) from exc

        return BankCheckResult(
            bank_payment_id=str(data.get("bank_payment_id") or bank_payment_id),
            amount=amount,
            status=status,
            paid_at=paid_at,
        )

    async def _post_json(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.base_url}/{endpoint}"
        last_error: Exception | None = None

        for _ in range(self.retries):
            try:
                async with AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(url, json=payload)

                if response.status_code >= 500:
                    raise BankTemporaryError(
                        f"bank API server error: {response.status_code}"
                    )
                if response.status_code >= 400:
                    raise BankPermanentError(
                        f"bank API request failed: {response.status_code}"
                    )

                body = response.json()
                if not isinstance(body, dict):
                    raise BankPermanentError("bank API returned non-JSON object")
                return body
            except BankTemporaryError as exc:
                last_error = exc
            except TimeoutException:
                last_error = BankTemporaryError("bank API timeout")
            except HTTPError as exc:
                last_error = BankTemporaryError(f"bank API transport error: {exc}")
            except ValueError as exc:
                raise BankPermanentError(f"invalid bank API response: {exc}") from exc

        if last_error is not None:
            raise last_error
        raise BankTemporaryError("bank API request failed")

    @staticmethod
    def _normalize_status(raw_status: str) -> BankPaymentState:
        status = raw_status.strip().upper()
        if status in {"PAID", "COMPLETED", "SUCCESS"}:
            return BankPaymentState.PAID
        if status in {"FAILED", "DECLINED", "CANCELED", "CANCELLED"}:
            return BankPaymentState.FAILED
        return BankPaymentState.PENDING
