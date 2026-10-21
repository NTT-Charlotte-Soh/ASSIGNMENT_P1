# Progress Log — `loan_calc` Bug Fixes

This document tracks the three confirmed seeded bugs, their fix requirements, regression tests, and current status.

---

## Confirmed Seeded Bugs

### Bug 1 — `_monthly_rate`: Premature rounding of monthly rate

| Field | Detail |
|---|---|
| **Location** | `calculator.py` → `_monthly_rate()` |
| **Problem** | `round(annual_rate / 1200, 4)` truncates the monthly rate to 4 decimal places before any calculation. For non-round rates such as 8.5 % p.a., the rounded value `0.0071` differs from the true value `0.00708333…`, causing EMI to deviate from the mathematically correct result. |
| **Expected fix** | Replace `round(annual_rate / 1200, 4)` with `annual_rate / 1200` |
| **Suggested regression test** | `test_emi_non_round_rate` — assert that `emi(1_000_000, 8.5, 240)` equals the independently derived value (calculated without rounding the monthly rate) |
| **Status** | ⏳ Not yet fixed |
| **Commit** | Pending |

---

### Bug 2 — `amortisation_schedule`: Off-by-one in loop range

| Field | Detail |
|---|---|
| **Location** | `calculator.py` → `amortisation_schedule()` |
| **Problem** | `range(1, tenure_months)` iterates months 1 through `tenure_months − 1` only. The final month is never appended. The schedule is one row short, the last row carries a non-zero residual balance, and the `if month == tenure_months` guard inside the loop is dead code. |
| **Expected fix** | Replace `range(1, tenure_months)` with `range(1, tenure_months + 1)` so the loop reaches the final month and the existing guard can execute to clear the balance exactly. |
| **Suggested regression test** | `test_schedule_row_count` — assert `len(amortisation_schedule(p, r, n)) == n` for representative inputs; `test_schedule_zero_final_balance` — assert the last row's `"balance"` is `0.0` |
| **Status** | ⏳ Not yet fixed |
| **Commit** | Pending |

---

### Bug 3 — `remaining_tenure`: Annual rate used instead of monthly rate

| Field | Detail |
|---|---|
| **Location** | `calculator.py` → `remaining_tenure()` |
| **Problem** | `r = annual_rate / 100` yields the annual decimal rate (e.g. `0.09` for 9 % p.a.). The remaining-periods formula requires the **monthly** decimal rate (`0.0075` for 9 % p.a.) when instalments are monthly. Using the annual rate produces an incorrect tenure that is far shorter than the correct value. The error propagates into `prepayment_savings`. |
| **Expected fix** | Replace `r = annual_rate / 100` with `r = _monthly_rate(annual_rate)` |
| **Suggested regression test** | `test_remaining_tenure_known_value` — assert `remaining_tenure(balance, rate, instalment)` equals a value independently computed using the monthly rate formula |
| **Status** | ⏳ Not yet fixed |
| **Commit** | Pending |

---

## Acceptance Tests Checklist

These tests must pass after all three bugs are fixed. Expected values must be derived independently (e.g. by hand calculation or a trusted reference implementation) and must **not** be copied from the current buggy code.

- [ ] `test_emi_standard` — ₹10,00,000 at 9 % p.a. for 240 months gives EMI within ₹8,997 ± ₹1
- [ ] `test_emi_zero_interest` — 0 % interest: EMI equals `principal / tenure_months`
- [ ] `test_emi_one_month` — one-month tenure: EMI equals principal (plus any interest for one period)
- [ ] `test_emi_large_principal` — very large principal (e.g. ₹10 crore) produces a finite, positive EMI
- [ ] `test_prepayment_larger_than_balance` — `prepay_amount` exceeding outstanding balance results in `months_left = 0` and `months_saved >= 0`
- [ ] `test_schedule_row_count` — `len(amortisation_schedule(p, r, n))` equals `n` for representative inputs
- [ ] `test_schedule_zero_final_balance` — the last row of the schedule has `"balance" == 0.0`
- [ ] `test_coverage` — test suite achieves at least 85 % line coverage across `loan_calc/calculator.py`

---

## Candidate Improvements and Stretch Goals

The following items were raised during review but are **not confirmed seeded bugs**. They may be addressed as optional enhancements after the three confirmed bugs are fixed.

| Item | Description |
|---|---|
| Negative `annual_rate` validation | No function rejects negative rates; silent incorrect output |
| `prepay_month` bounds check | Out-of-range value raises unhandled `IndexError` instead of a descriptive `ValueError` |
| `schedule_to_csv` encoding | Missing `newline=""` argument may produce double carriage returns on Windows |
| `total_payment` schedule consistency | Multiplication `emi × tenure_months` may differ by a few pence from the sum of actual schedule instalments |
| `compare_offers` / `eligible_amount` validation | Missing dict keys raise `KeyError`; invalid FOIR or negative income produces misleading results silently |
| Custom exception types | `LoanInputError` (or similar) would help callers distinguish domain errors from general Python errors |
