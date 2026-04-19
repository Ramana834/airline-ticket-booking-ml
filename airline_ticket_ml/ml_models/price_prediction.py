from __future__ import annotations

from datetime import date, datetime
from django.utils.dateparse import parse_date

from flights.models import Flight


def predict_price(price: float) -> float:
    """Legacy helper (kept for compatibility)."""
    return float(price) + 500


def predict_price_trend(origin: str, destination: str, depart_date: str):
    """
    Dynamic Fare Prediction (simple baseline):
    - Uses current flight data in DB as 'historical' proxy
    - Returns (trend, confidence, best_price)

    trend: 'RISE' or 'FALL'
    confidence: 0-100 integer
    best_price: min available price for the query (or None)
    """
    dt = parse_date(depart_date)
    qs = Flight.objects.filter(source__iexact=origin, destination__iexact=destination)
    if dt:
        qs = qs.filter(date=dt)

    prices = list(qs.values_list("price", flat=True))
    best_price = min(prices) if prices else None

    # heuristic: closer date => more likely to rise
    days_to = None
    if dt:
        days_to = (dt - date.today()).days

    if days_to is not None and days_to <= 7:
        trend = "RISE"
    else:
        trend = "FALL"

    # confidence from sample size
    n = len(prices)
    confidence = min(95, 40 + n * 10) if n else 35

    return trend, confidence, best_price
