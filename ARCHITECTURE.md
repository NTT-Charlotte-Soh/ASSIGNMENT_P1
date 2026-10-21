# Architecture — `loan_calc`

## Purpose

`loan_calc` is a pure-Python library for home and personal loan arithmetic. Its core capabilities are:

- **EMI calculation** — fixed monthly instalment using the standard reducing-balance formula.
- **Amortisation schedule generation** — month-by-month breakdown of interest, principal repaid, and outstanding balance.
- **Prepayment / tenure-saving calculation** — effect of a lump-sum mid-loan payment, keeping EMI constant and shortening the remaining tenure.

Supporting utilities cover loan-eligibility estimation, multi-offer comparison, Indian-Rupee formatting, CSV export, and a display-ready summary.

---

## Repository Structure

```
ASSIGNMENT_P1/
├── loan_calc/
│   ├── __init__.py        # Re-exports every public name via `from .calculator import *`
│   └── calculator.py      # All calculation logic; stdlib only (math, datetime)
├── cli.py                 # Thin argparse CLI — calls summary(), amortisation_schedule(), prepayment_savings()
├── tests/                 # Placeholder only (.gitkeep); no tests currently exist
├── requirements.txt
└── ARCHITECTURE.md
```

---

## Rate Conversion

All reducing-balance formulas require a **monthly decimal rate** derived from the annual percentage rate:

```
monthly_rate = annual_rate / 1200
```

For example, 9 % p.a. → `9 / 1200 = 0.0075`.

> **Current implementation note:** `_monthly_rate()` applies `round(..., 4)` to this result before returning it. This premature rounding is a confirmed seeded bug (see § Confirmed Seeded Bugs). The intended production value is the unrounded quotient.

---

## Public API

### `_monthly_rate(annual_rate) → float`

**Private helper.** Converts an annual percentage rate to a monthly decimal rate.

Current (buggy) implementation:
```python
r = round(annual_rate / 1200, 4)
```

Intended production implementation:
```python
r = annual_rate / 1200
```

Used by `emi()`, `amortisation_schedule()`, and `eligible_amount()`.

---

### `emi(principal, annual_rate, tenure_months) → float`

Calculates the fixed monthly instalment.

| Parameter | Meaning |
|---|---|
| `principal` | Loan amount |
| `annual_rate` | Annual interest rate as a percentage (e.g. `8.5` for 8.5 % p.a.) |
| `tenure_months` | Loan duration in months |

**Validation:**
- Raises `ValueError("tenure must be positive")` if `tenure_months <= 0`.
- Raises `ValueError("principal must be positive")` if `principal <= 0`.

**Zero-rate branch:** when `_monthly_rate` returns `0`, the function returns `round(principal / tenure_months, 2)` — equal principal instalments with no interest.

**Normal branch:**
```
r  = _monthly_rate(annual_rate)
f  = (1 + r) ^ tenure_months
EMI = principal × r × f / (f − 1)
```

Result is rounded to 2 decimal places.

---

### `total_payment(principal, annual_rate, tenure_months) → float`

Returns `round(emi(...) × tenure_months, 2)`. Computed by simple multiplication; does not derive the total from the schedule.

---

### `total_interest(principal, annual_rate, tenure_months) → float`

Returns `round(total_payment(...) − principal, 2)`.

---

### `amortisation_schedule(principal, annual_rate, tenure_months) → list[dict]`

Generates a month-by-month repayment table.

**Each row dict contains:**

| Key | Value |
|---|---|
| `"month"` | Month number (1-based) |
| `"emi"` | Instalment paid this month |
| `"interest"` | `round(opening_balance × monthly_rate, 2)` |
| `"principal"` | `round(emi − interest, 2)` |
| `"balance"` | `max(round(opening_balance − principal_component, 2), 0.0)` |

**Amortisation flow:**
- Opening balance for month 1 is `principal`.
- Each month: interest is charged on the opening balance; the remainder of the instalment reduces principal; the closing balance becomes the next month's opening balance.
- **Final-payment handling:** the loop contains a guard `if month == tenure_months` that sets the last instalment to exactly clear the remaining balance. Due to the seeded off-by-one bug this guard is currently unreachable (see § Confirmed Seeded Bugs). Once fixed, the final row will show a zero closing balance and an instalment that may differ slightly from the constant EMI.

**Current behaviour (bugged):** the loop is `range(1, tenure_months)`, so it iterates months 1 through `tenure_months − 1`. The schedule is one row short and the last row carries a small residual balance.

---

### `outstanding_after(principal, annual_rate, tenure_months, months_paid) → float`

Returns the outstanding balance after `months_paid` instalments.

- `months_paid <= 0` → `round(principal, 2)`
- `months_paid > len(schedule)` → `0.0`
- Otherwise → `schedule[months_paid − 1]["balance"]`

Inherits the off-by-one behaviour of `amortisation_schedule`.

---

### `remaining_tenure(balance, annual_rate, instalment) → int`

Estimates the number of monthly instalments needed to repay `balance`.

**Intended formula** (standard remaining-periods formula with monthly rate):
```
r  = _monthly_rate(annual_rate)     # monthly decimal rate
n  = −log(1 − balance × r / instalment) / log(1 + r)
return ceil(n)
```

**Current (buggy) implementation** uses `r = annual_rate / 100`, which is the annual decimal rate. This produces an incorrect (far shorter) tenure estimate and propagates the error into `prepayment_savings`. See § Confirmed Seeded Bugs.

- `balance <= 0` → returns `0`.
- `annual_rate == 0` → returns `ceil(balance / instalment)`.
- `instalment <= balance × r` → raises `ValueError("instalment too small to repay the loan")`.

---

### `prepayment_savings(principal, annual_rate, tenure_months, prepay_month, prepay_amount) → dict`

Models a lump-sum prepayment strategy: **keep the EMI unchanged, shorten the remaining tenure**.

| Parameter | Meaning |
|---|---|
| `principal` | Original loan amount |
| `annual_rate` | Annual interest rate (%) |
| `tenure_months` | Original tenure in months |
| `prepay_month` | Month after which the lump sum is applied (1-based, references the schedule balance at end of that month) |
| `prepay_amount` | Lump-sum prepayment amount |

**Returns:**

| Key | Meaning |
|---|---|
| `"emi"` | Original monthly instalment (unchanged) |
| `"months_saved"` | Months eliminated from the original remaining tenure |
| `"new_tenure"` | Revised total tenure (`prepay_month + months_left`) |
| `"interest_saved"` | Reduction in total interest paid, rounded to 2 dp |
| `"interest_paid_before_prepayment"` | Sum of interest paid in months 1 through `prepay_month` |

**Flow:**
1. Retrieve outstanding balance at end of `prepay_month` from the schedule.
2. Subtract `prepay_amount` → `new_balance`.
3. If `new_balance <= 0`, the loan is fully cleared (`months_left = 0`).
4. Otherwise call `remaining_tenure(new_balance, annual_rate, instalment)` to estimate months remaining.
5. Compute interest saved vs. `total_interest(...)`.

`prepayment_savings` inherits both the amortisation off-by-one and the incorrect rate in `remaining_tenure`.

---

### `compare_offers(principal, offers) → list[dict]`

Accepts a list of offer dicts (`bank`, `rate`, `tenure`, optional `processing_fee_pct`). Returns a list sorted by `total_cost` (total interest + processing fee) ascending. Each output dict contains `bank`, `emi`, `total_interest`, `processing_fee`, `total_cost`.

---

### `eligible_amount(monthly_income, existing_emis, annual_rate, tenure_months, foir=0.5) → float`

Estimates the maximum eligible principal using the Fixed Obligation to Income Ratio (default 50 %).

```
available_emi = monthly_income × foir − existing_emis
```

If `available_emi <= 0`, returns `0.0`. Otherwise applies the inverse EMI formula to derive the principal.

---

### `format_inr(amount) → str`

Formats a number using Indian numbering conventions: last 3 digits together, then groups of 2, prefixed with `₹`. Handles negatives and rounds to 2 decimal places before formatting.

---

### `schedule_to_csv(rows, path)`

Writes a schedule row list to a CSV file. Column order: `month, emi, interest, principal, balance`. Opens in text write mode (`"w"`) with no explicit `newline` argument.

---

### `summary(principal, annual_rate, tenure_months, start=None) → dict`

Returns a display-ready dict with formatted string values.

| Key | Format |
|---|---|
| `"principal"` | `format_inr(principal)` |
| `"rate"` | `"{annual_rate}% p.a."` |
| `"tenure"` | `"{tenure_months} months"` |
| `"emi"` | `format_inr(emi(...))` |
| `"total_interest"` | `format_inr(total_interest(...))` |
| `"total_payment"` | `format_inr(total_payment(...))` |
| `"last_emi"` | Calendar month `tenure_months` after `start` (defaults to `date.today()`) |
| `"currency"` | `"INR"` |

---

## Confirmed Seeded Bugs

These three defects are intentionally present in the starter implementation. No other issues are classified as confirmed bugs.

### Bug 1 — `_monthly_rate`: Premature rounding of monthly rate

**Location:** `calculator.py` → `_monthly_rate()`

**Current code:**
```python
r = round(annual_rate / 1200, 4)
```

**Problem:** Rounding to 4 decimal places before any calculation introduces truncation error into the monthly rate. For non-round annual rates such as 8.5 %, the rounded rate `0.0071` differs from the true rate `0.00708333…`, causing the computed EMI to deviate from the mathematically correct value.

**Required fix:**
```python
r = annual_rate / 1200
```

---

### Bug 2 — `amortisation_schedule`: Off-by-one in loop range

**Location:** `calculator.py` → `amortisation_schedule()`

**Current code:**
```python
for month in range(1, tenure_months):
```

**Problem:** The loop runs from month 1 to `tenure_months − 1` inclusive. The final month is never appended to the schedule. For a 12-month loan the schedule contains only 11 rows and the closing balance of the last row is a non-zero residual. The inner guard `if month == tenure_months` is unreachable dead code.

**Required fix:**
```python
for month in range(1, tenure_months + 1):
```

---

### Bug 3 — `remaining_tenure`: Annual rate used in place of monthly rate

**Location:** `calculator.py` → `remaining_tenure()`

**Current code:**
```python
r = annual_rate / 100
```

**Problem:** The remaining-periods formula requires the **monthly** rate when instalments are monthly. Using the annual decimal rate (e.g. `0.09` for 9 % p.a.) instead of the monthly rate (`0.0075`) produces a drastically shorter and incorrect tenure estimate. This error propagates into `prepayment_savings`.

**Required fix:**
```python
r = _monthly_rate(annual_rate)
```

---

## Candidate Improvements and Stretch Goals

The following concerns were identified during review but are **not confirmed seeded bugs**. They represent optional hardening and clean-up work.

- **Negative `annual_rate` validation:** no function rejects negative rates; a guard in `_monthly_rate` or `emi` would protect all callers.
- **`prepay_month` bounds check in `prepayment_savings`:** an out-of-range value raises an unhandled `IndexError`; a descriptive `ValueError` would be cleaner.
- **`schedule_to_csv` encoding:** the missing `newline=""` argument can produce double carriage returns on Windows; wrapping the write in a `try/except OSError` would improve robustness.
- **`total_payment` schedule consistency:** the current multiplication `emi × tenure_months` does not sum actual schedule instalments; after Bug 2 is fixed a small rounding discrepancy may remain.
- **`compare_offers` / `eligible_amount` input validation:** missing keys in an offer dict raise an unhandled `KeyError`; negative income or invalid FOIR silently produce misleading results.
- **Custom exception types:** using domain-specific exceptions (e.g. `LoanInputError`) instead of bare `ValueError` would allow callers to distinguish loan-domain errors from other failures.
