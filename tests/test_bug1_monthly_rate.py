"""
Regression test for Confirmed Seeded Bug 1:
  _monthly_rate() rounds the monthly rate to four decimal places before EMI
  calculation, producing incorrect results for non-round annual rates.

Expected behaviour after fix:
  _monthly_rate(annual_rate) returns annual_rate / 1200 without rounding.

This test:
  - calls the public emi() function (not the private helper directly);
  - uses a non-round annual rate of 8.5 % p.a.;
  - asserts the EMI is approximately 8678.23 (independently calculated);
  - FAILS on the starter implementation where round(annual_rate / 1200, 4)
    rounds 0.00708333... to 0.0071, shifting the EMI to approximately 8691;
  - PASSES once _monthly_rate() returns annual_rate / 1200 without rounding.
"""

import pytest

from loan_calc import emi


def test_emi_non_round_rate():
    """EMI for 8.5% p.a. must use the unrounded monthly rate 8.5/1200."""
    # Independent derivation:
    #   r = 8.5 / 1200 = 0.00708333...
    #   f = (1 + r)^240
    #   EMI = 1_000_000 * r * f / (f - 1) ≈ 8678.23
    #
    # Buggy implementation rounds r to 0.0071, giving EMI ≈ 8691 — outside
    # the tolerance below and therefore causes this test to fail.
    result = emi(principal=1_000_000, annual_rate=8.5, tenure_months=240)
    assert result == pytest.approx(8678.23, abs=0.005)
