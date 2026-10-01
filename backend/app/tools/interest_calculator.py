from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, Field

DEFAULT_ANNUAL_INTEREST_RATE = Decimal("0.18")  # 18% per annum under Section 50(1)

class InterestCalculationResult(BaseModel):
    principal: Decimal
    annual_rate: Decimal
    delay_days: int
    calculated_interest: Decimal
    daily_rate: Decimal

def calculate_section_50_interest(
    principal_tax: Decimal,
    delay_days: int,
    annual_rate: Decimal = DEFAULT_ANNUAL_INTEREST_RATE
) -> InterestCalculationResult:
    """
    Deterministically computes simple statutory interest under Section 50 of the CGST Act.
    Formula: Interest = Principal * Annual_Rate * (Delay_Days / 365)
    All monetary arithmetic is performed using Python Decimal.
    """
    if principal_tax <= Decimal("0.00") or delay_days <= 0:
        return InterestCalculationResult(
            principal=round(max(Decimal("0.00"), principal_tax), 2),
            annual_rate=annual_rate,
            delay_days=max(0, delay_days),
            calculated_interest=Decimal("0.00"),
            daily_rate=round(annual_rate / Decimal("365"), 6)
        )
    
    principal = round(principal_tax, 2)
    daily_rate = annual_rate / Decimal("365")
    raw_interest = principal * annual_rate * Decimal(delay_days) / Decimal("365")
    calculated_interest = raw_interest.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    return InterestCalculationResult(
        principal=principal,
        annual_rate=annual_rate,
        delay_days=delay_days,
        calculated_interest=calculated_interest,
        daily_rate=round(daily_rate, 6)
    )
