from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, model_validator

CHART_OF_ACCOUNTS: dict[int, str] = {
    1000: "Cash",
    1100: "Accounts Receivable",
    2000: "Accounts Payable",
    4000: "Revenue",
    5000: "Expense",
}


class PartnerType(str, Enum):
    CUSTOMER = "customer"
    VENDOR = "vendor"


class Partner(BaseModel):
    id: int
    name: str
    type: PartnerType


class JournalLine(BaseModel):
    account_code: int
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")

    @model_validator(mode="after")
    def validate_line(self) -> JournalLine:
        if self.account_code not in CHART_OF_ACCOUNTS:
            raise ValueError(f"Unknown account code: {self.account_code}")
        has_debit = self.debit > 0
        has_credit = self.credit > 0
        if has_debit == has_credit:
            raise ValueError(
                "Each journal line must have exactly one non-zero side (debit or credit)"
            )
        return self


class JournalEntry(BaseModel):
    id: int
    date: date
    description: str
    partner_id: int | None = None
    lines: list[JournalLine] = Field(..., min_length=2)

    @model_validator(mode="after")
    def must_balance(self) -> JournalEntry:
        total_debit = sum(ln.debit for ln in self.lines)
        total_credit = sum(ln.credit for ln in self.lines)
        if total_debit != total_credit:
            raise ValueError(
                f"Journal entry does not balance: DR {total_debit} ≠ CR {total_credit}"
            )
        return self


class AppState(BaseModel):
    partners: list[Partner] = Field(default_factory=list)
    entries: list[JournalEntry] = Field(default_factory=list)
