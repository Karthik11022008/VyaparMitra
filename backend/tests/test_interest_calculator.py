from decimal import Decimal
from backend.app.tools.interest_calculator import calculate_section_50_interest

def test_interest_zero_delay():
    res = calculate_section_50_interest(
        principal_tax=Decimal("10000.00"),
        delay_days=0,
        annual_rate=Decimal("0.18")
    )
    assert res.calculated_interest == Decimal("0.00")
    assert res.delay_days == 0

def test_interest_one_day():
    # 10,000 * 0.18 * (1/365) = 4.9315 -> 4.93
    res = calculate_section_50_interest(
        principal_tax=Decimal("10000.00"),
        delay_days=1,
        annual_rate=Decimal("0.18")
    )
    assert res.calculated_interest == Decimal("4.93")

def test_interest_full_year():
    # 10,000 * 0.18 * (365/365) = 1,800.00
    res = calculate_section_50_interest(
        principal_tax=Decimal("10000.00"),
        delay_days=365,
        annual_rate=Decimal("0.18")
    )
    assert res.calculated_interest == Decimal("1800.00")

def test_interest_normal_delay():
    # 54,000 * 0.18 * (60/365) = 1597.808 -> 1597.81
    res = calculate_section_50_interest(
        principal_tax=Decimal("54000.00"),
        delay_days=60,
        annual_rate=Decimal("0.18")
    )
    assert res.calculated_interest == Decimal("1597.81")

def test_interest_zero_principal():
    res = calculate_section_50_interest(
        principal_tax=Decimal("0.00"),
        delay_days=30
    )
    assert res.calculated_interest == Decimal("0.00")
