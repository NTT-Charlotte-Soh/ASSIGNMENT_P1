# Prompt Log — AI-Assisted Review Decisions

This file records decisions made during the AI-assisted documentation review of `loan_calc`, including corrections applied and suggestions that were rejected or reclassified.

---

## Review Session — Initial Documentation Pass

### What the AI review got right

- Correctly identified the `amortisation_schedule` off-by-one: the loop `range(1, tenure_months)` omits the final month, leaving dead code inside the loop unreachable.
- Correctly identified that `remaining_tenure` uses `annual_rate / 100` (annual decimal rate) where a monthly rate is required.
- Accurately described the return structure and calculation flow for all public functions.

---

### Mistake — Premature monthly-rate rounding not identified as a seeded bug

**Finding:** The initial review described `_monthly_rate` rounding to four decimal places as a general accuracy note ("can introduce small cumulative errors in long schedules") rather than recognising it as a confirmed seeded EMI bug.

**Why this was wrong:** For non-round annual rates such as 8.5 % p.a., rounding `annual_rate / 1200` to 4 decimal places changes the monthly rate from `0.00708333…` to `0.0071` — a discrepancy that directly produces an incorrect EMI output. This is a functional defect, not merely a precision concern. It is one of the three intentionally seeded bugs in the starter implementation.

**Correction applied:** `_monthly_rate` premature rounding is now listed as **Confirmed Seeded Bug 1** in both `ARCHITECTURE.md` and `PROGRESS.md`.

---

### Rejected suggestions — Unproven concerns treated as confirmed bugs

The initial `PROGRESS.md` listed eight bugs. Five of those entries described concerns that are real code-quality issues but are **not confirmed seeded defects**:

| Rejected entry | Reason for reclassification |
|---|---|
| No `annual_rate` negativity check | Unvalidated input that produces silent wrong output — a hardening concern, not a seeded calculation bug |
| `prepay_month` not bounds-checked | Missing guard that raises `IndexError` — a robustness concern, not a seeded calculation bug |
| `schedule_to_csv` `newline=""` / no error handling | Platform encoding edge case and missing exception handling — a portability concern, not a seeded calculation bug |
| `total_payment` not summing schedule rows | Approximation that can differ by a small rounding amount — relevant only after Bug 2 is fixed; not independently seeded |
| `compare_offers` / `eligible_amount` missing validation | Defensive programming gap — not a seeded calculation bug |

**Correction applied:** These five items were moved to the **"Candidate Improvements and Stretch Goals"** section in both `ARCHITECTURE.md` and `PROGRESS.md`. Only the three confirmed seeded calculation defects remain in the confirmed-bugs section.

---

### Rejected suggestion — PROGRESS.md should be git-ignored

The previous session added `PROGRESS.md` to `.gitignore` on the basis that it is a "local progress / notes" file.

**Why this was wrong:** `PROGRESS.md` records debugging evidence, confirmed bug status, fix commits, and acceptance test outcomes. This information is relevant to the assignment's acceptance criteria and should be version-controlled alongside the code. Ignoring it removes the audit trail.

**Correction required:** `PROGRESS.md` should be removed from `.gitignore` so that it is tracked, committed, and pushed with the rest of the project.

---

## Guidance for Future Test Implementation

Regression tests must use **independently derived** expected values. They must not call the current (buggy) implementation to generate expected outputs, because doing so would encode the defect into the test assertion and the test would pass even when the bug is present.

Example: the expected EMI for ₹10,00,000 at 9 % p.a. for 240 months should be calculated by hand or with a verified external tool before being written into the test, not by running `emi(1_000_000, 9, 240)` in the current codebase.
