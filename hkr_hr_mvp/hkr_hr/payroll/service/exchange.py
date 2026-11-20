"""Simple HR-maintained rates for display totals; source pay remains unchanged."""
from decimal import Decimal, InvalidOperation

from hkr_hr.references.api import reference_options


def valid_rate(value):
    try:
        rate = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Invalid exchange rate") from None
    if not rate.is_finite() or not Decimal("0") < rate <= Decimal("1000000"):
        raise ValueError("Invalid exchange rate")
    return rate


def exchange_settings():
    return [{"currency": ref.code, "rate": (ref.metadata_json or {}).get("payroll_hkd_rate", "")}
            for ref in reference_options("currency") if ref.code != "HKD"]


def hkd_summary(items):
    rates = {item["currency"]: item["rate"] for item in exchange_settings()}
    rates["HKD"] = "1"
    totals, missing = {}, []
    for item in items:
        currency = item["currency"]
        try:
            rate = valid_rate(rates.get(currency, ""))
        except ValueError:
            missing.append(currency)
            continue
        for key, amount in item.items():
            if key != "currency":
                totals[key] = totals.get(key, Decimal("0")) + amount * rate
    return {"totals": {} if missing else totals, "missing": sorted(set(missing))}
