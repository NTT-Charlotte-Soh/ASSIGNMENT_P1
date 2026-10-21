# Architecture — `loan_calc`

## Purpose

`loan_calc` is a pure-Python module for home/personal loan arithmetic. It provides:

- **EMI calculation** – monthly instalment using the standard reducing-balance formula.
- **Amortisation schedule generation** – month-by-month breakdown of interest, principal, and outstanding balance.
- **Prepayment / savings calculation** – effect of a lump-sum mid-loan prepayment on remaining tenure and total interest, assuming the EMI is kept constant.
- Supporting utilities: loan-eligibility estimation, multi-offer comparison, Indian-Rupee formatting, CSV export, and a human-readable summary.

---

## Repository Structure

```
ASSIGNMENT_P1/
├── loan_calc/
│   ├── __init__.py        # Re-exports every public name from calculator.py via `from .calculator import *`
│   └── calculator.py      # All calculation logic; single module, no external dependencies beyond stdlib
├── cli.py                 # Thin argparse CLI that calls summary(), amortisation_schedule(), prepayment_savings()
├── requirements.txt
└── ARCHITECTURE.md
```

`tests/` contains only a `.gitkeep` placeholder — no tests are present.

---

## Public API

### `_monthly_rate(annual_rate)`

**Private helper.** Converts an annual interest rate (expressed as a percentage, e.g. `12` for 12 % p.a.) to a monthly decimal rate.

```
monthly_rate = round(annual_rate / 1200, 4)
```

- Result is rounded to 4 decimal places before being used downstream. This rounding can introduce small cumulative errors in long schedules.
- Returns `0.0` when `annual_rate` is `0`.

---

### `emi(principal, annual_rate, tenure_months) → float`

Calculates the fixed monthly instalment.

| Parameter | Type | Meaning |
|---|---|---|
| `principal` | `float` | Loan amount (any currency unit) |
| `annual_rate` | `float` | Annual interest rate as a percentage (e.g. `8.5` for 8.5 %) |
| `tenure_months` | `int` | Loan duration in months |

**Returns** a `float` rounded to 2 decimal places.

**Validation:**
- Raises `ValueError("tenure must be positive")` if `tenure_months <= 0`.
- Raises `ValueError("principal must be positive")` if `principal <= 0`.
- `annual_rate` is **not validated**; zero and negative values are accepted silently.

**Zero-rate branch:** when `annual_rate` resolves to a monthly rate of `0`, the function returns `round(principal / tenure_months, 2)` — equal principal instalments with no interest component.

**Normal branch (r > 0):**
```
f = (1 + r) ^ tenure_months
EMI = principal × r × f / (f − 1)
```

---

### `total_payment(principal, annual_rate, tenure_months) → float`

Returns `round(emi(...) × tenure_months, 2)`.

This is a simple multiplication; it does **not** derive the sum from the amortisation schedule. As a result it does not reflect any last-instalment rounding adjustment that the schedule might produce.

---

### `total_interest(principal, annual_rate, tenure_months) → float`

Returns `round(total_payment(...) − principal, 2)`.

---

### `amortisation_schedule(principal, annual_rate, tenure_months) → list[dict]`

Generates a month-by-month repayment breakdown.

**Returns** a list of dicts, each with:

| Key | Meaning |
|---|---|
| `"month"` | Month number (1-based) |
| `"emi"` | Instalment paid this month |
| `"interest"` | Interest component: `round(opening_balance × monthly_rate, 2)` |
| `"principal"` | Principal component: `round(emi − interest, 2)` |
| `"balance"` | Closing balance: `max(round(opening_balance − principal_component, 2), 0.0)` |

**Known limitation — off-by-one:** the loop is `range(1, tenure_months)`, which iterates months `1` through `tenure_months − 1`. **The final month is never appended to the schedule.** The inner guard `if month == tenure_months` is unreachable dead code; the last-instalment adjustment it was intended to apply never executes.

Consequently, for a 12-month loan the schedule contains 11 rows, and the balance in the last row is typically a small residual rather than zero.

---

### `outstanding_after(principal, annual_rate, tenure_months, months_paid) → float`

Returns the outstanding balance after `months_paid` instalments have been made.

- If `months_paid <= 0`: returns `round(principal, 2)`.
- If `months_paid > len(schedule)`: returns `0.0`.
- Otherwise returns `schedule[months_paid − 1]["balance"]`.

Inherits the off-by-one limitation of `amortisation_schedule`.

---

### `remaining_tenure(balance, annual_rate, instalment) → int`

Estimates the number of months required to repay `balance` at the given `instalment`.

**Calculation:**
```
r = annual_rate / 100          # annual rate as a decimal — NOT the monthly rate
n = −log(1 − balance × r / instalment) / log(1 + r)
return ceil(n)
```

- Returns `0` if `balance <= 0`.
- If `annual_rate` is `0`, returns `ceil(balance / instalment)`.
- Raises `ValueError("instalment too small to repay the loan")` if `instalment <= balance × r`.

**Known limitation — incorrect rate conversion:** this function divides `annual_rate` by `100`, yielding an annual decimal rate, while every other function in the module uses `_monthly_rate` (which divides by `1200`) for the same formula. The formula for remaining periods requires a **monthly** rate when instalments are monthly. Using the annual rate produces an incorrect (shorter) tenure estimate. This bug propagates into `prepayment_savings`.

---

### `prepayment_savings(principal, annual_rate, tenure_months, prepay_month, prepay_amount) → dict`

Calculates the benefit of making a lump-sum prepayment at a specific month. The strategy assumed is: **keep the EMI unchanged and shorten the remaining tenure**.

| Parameter | Meaning |
|---|---|
| `principal` | Original loan principal |
| `annual_rate` | Annual interest rate (%) |
| `tenure_months` | Original tenure in months |
| `prepay_month` | Month number after which the prepayment is applied (1-based) |
| `prepay_amount` | Lump-sum amount prepaid |

**Returns** a dict:

| Key | Meaning |
|---|---|
| `"emi"` | Monthly instalment (unchanged after prepayment) |
| `"months_saved"` | Reduction in remaining months vs. the original schedule |
| `"new_tenure"` | Revised total tenure in months (`prepay_month + months_left`) |
| `"interest_saved"` | Reduction in total interest paid, rounded to 2 dp |
| `"interest_paid_before_prepayment"` | Sum of interest rows up to and including `prepay_month` |

**Flow:**
1. Fetches the outstanding balance at `prepay_month` from the amortisation schedule.
2. Subtracts `prepay_amount` to get `new_balance`.
3. If `new_balance <= 0`, the loan is fully repaid (`months_left = 0`).
4. Otherwise calls `remaining_tenure(new_balance, annual_rate, instalment)` to estimate remaining months.
5. Computes savings relative to `total_interest(...)`.

**No input validation:** `prepay_month` is not checked against the schedule length; values out of range will cause an `IndexError`. `prepay_amount` is not checked for negative values.

Inherits the incorrect rate conversion from `remaining_tenure`.

---

### `compare_offers(principal, offers) → list[dict]`

Compares loan offers from multiple banks and sorts them by total cost (ascending).

`offers` is a list of dicts, each with:

| Key | Required | Meaning |
|---|---|---|
| `"bank"` | Yes | Bank name (label only) |
| `"rate"` | Yes | Annual interest rate (%) |
| `"tenure"` | Yes | Tenure in months |
| `"processing_fee_pct"` | No | Processing fee as a percentage of principal (defaults to `0`) |

**Returns** a list of dicts sorted by `total_cost` ascending:

| Key | Meaning |
|---|---|
| `"bank"` | Bank name |
| `"emi"` | Monthly instalment |
| `"total_interest"` | Total interest over the full tenure |
| `"processing_fee"` | `round(processing_fee_pct × principal / 100, 2)` |
| `"total_cost"` | `round(total_interest + processing_fee, 2)` |

No validation is performed on the `offers` list or its entries.

---

### `eligible_amount(monthly_income, existing_emis, annual_rate, tenure_months, foir=0.5) → float`

Estimates the maximum loan principal a borrower can be approved for, based on the Fixed Obligation to Income Ratio (FOIR).

```
available_emi = monthly_income × foir − existing_emis
```

- If `available_emi <= 0`, returns `0.0`.
- If `annual_rate` is `0`, returns `round(available_emi × tenure_months, 2)`.
- Otherwise applies the inverse EMI formula:
  ```
  f = (1 + r) ^ tenure_months
  eligible = available_emi × (f − 1) / (r × f)
  ```
- Default FOIR is `0.5` (50 %).
- No validation of inputs.

---

### `format_inr(amount) → str`

Formats a number using the Indian numbering system.

- Prefixes with `₹`.
- Groups the last 3 digits, then groups subsequent digits in pairs (e.g. `₹12,34,567.89`).
- Handles negative amounts with a leading `-`.
- Rounds to 2 decimal places before formatting.

---

### `schedule_to_csv(rows, path)`

Writes the list of dicts returned by `amortisation_schedule` to a CSV file at `path`.

- Column order: `month, emi, interest, principal, balance`.
- Opens the file in text write mode (`"w"`); no `newline=""` argument is passed, so on Windows the file will contain `\r\n` line endings.
- No error handling; any `IOError` propagates to the caller.
- No return value.

---

### `summary(principal, annual_rate, tenure_months, start=None) → dict`

Returns a human-readable summary dict suitable for display or JSON serialisation.

- `start` defaults to `date.today()` when not provided.
- Computes the last-EMI year/month by adding `tenure_months` to `start`.
- All monetary fields are formatted via `format_inr`.

**Returns:**

| Key | Example value |
|---|---|
| `"principal"` | `"₹5,00,000.00"` |
| `"rate"` | `"8.5% p.a."` |
| `"tenure"` | `"120 months"` |
| `"emi"` | `"₹6,187.27"` |
| `"total_interest"` | `"₹2,42,472.40"` |
| `"total_payment"` | `"₹7,42,472.40"` |
| `"last_emi"` | `"2036-10"` |
| `"currency"` | `"INR"` |

---

## Calculation Flow Summary

### 1. Rate conversion
`annual_rate %` → `round(annual_rate / 1200, 4)` = monthly decimal rate.  
All schedule and EMI functions use this value.

### 2. EMI calculation
```
r  = _monthly_rate(annual_rate)
f  = (1 + r) ^ tenure_months
EMI = principal × r × f / (f − 1)    # when r > 0
EMI = principal / tenure_months        # when r == 0
```
Result rounded to 2 dp.

### 3. Monthly amortisation logic
For each month `m` in `1 … tenure_months − 1` (see off-by-one limitation):
```
interest_m       = round(balance_{m-1} × r, 2)
principal_paid_m = round(EMI − interest_m, 2)
balance_m        = max(round(balance_{m-1} − principal_paid_m, 2), 0.0)
```
Opening balance for month 1 is `principal`.

### 4. Prepayment application
After `prepay_month` months, a lump sum reduces the outstanding balance:
```
new_balance = schedule[prepay_month − 1]["balance"] − prepay_amount
```
The original EMI is kept; `remaining_tenure` estimates how many more months are needed to clear `new_balance`. The difference vs. the original remaining months is `months_saved`.

---

## Rounding and Currency

- EMI and all monetary outputs are rounded to **2 decimal places** using Python's built-in `round()`.
- `_monthly_rate` is rounded to **4 decimal places**, which can cause small per-period rounding drift in long-tenor schedules.
- The module defines `DEFAULT_CURRENCY = "INR"` and uses `₹` in `format_inr`, but no currency conversion or enforcement is applied to inputs; amounts are treated as plain numbers.

---

## Input Validation

Only `emi()` performs explicit input checks:
- `tenure_months <= 0` → `ValueError`
- `principal <= 0` → `ValueError`

`remaining_tenure()` raises `ValueError("instalment too small to repay the loan")` when `instalment <= balance × r`.

All other functions perform **no input validation**. Invalid or nonsensical inputs (negative rates, zero income, out-of-range months) will either produce silently incorrect results or raise an unhandled exception from Python builtins (e.g. `IndexError`, `ZeroDivisionError`, `ValueError` from `math.log`).

---

## Known Limitations and Risks

| # | Location | Description |
|---|---|---|
| 1 | `amortisation_schedule` | Loop `range(1, tenure_months)` omits the final month. The last row shows a non-zero residual balance. The `if month == tenure_months` guard inside the loop is dead code. |
| 2 | `remaining_tenure` | Uses `annual_rate / 100` (annual decimal) instead of the monthly rate `annual_rate / 1200`. The standard remaining-periods formula requires the **monthly** rate for monthly instalments. Results are numerically incorrect and this error propagates to `prepayment_savings`. |
| 3 | `total_payment` | Computed as `emi × tenure_months` rather than the sum of actual schedule instalments. Does not reflect any last-instalment rounding discrepancy. |
| 4 | `annual_rate` validation | No function validates that `annual_rate` is non-negative. A negative rate will silently produce a negative monthly rate and mathematically plausible-looking but economically invalid outputs. |
| 5 | `prepayment_savings` | `prepay_month` is not bounds-checked. If `prepay_month` exceeds `len(amortisation_schedule(...))`, an `IndexError` is raised. |
| 6 | `schedule_to_csv` | No exception handling. On Windows, line endings will be `\r\n` rather than `\n` due to the missing `newline=""` argument to `open()`. |
| 7 | Tests | No test suite exists (`tests/` contains only `.gitkeep`). Correctness of all functions is unverified. |
| 8 | `compare_offers` / `eligible_amount` | No validation of offer structure or income inputs. Missing required keys in an offer dict raise an unhandled `KeyError`. |
