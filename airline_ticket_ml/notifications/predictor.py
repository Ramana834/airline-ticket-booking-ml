from datetime import date, datetime
from .festival_calendar import festival_boost  # ✅ correct import


def predict_price(base_price: float, depart_date):
    """
    Rule-based + festival demand logic
    depart_date can be date OR "YYYY-MM-DD"
    """

    # ✅ convert depart_date into python date
    if isinstance(depart_date, date):
        d = depart_date
    else:
        try:
            d = datetime.strptime(str(depart_date), "%Y-%m-%d").date()
        except ValueError:
            d = date.today()

    # ✅ Normal increase (testing ki konchem high pettanu)
    normal_increase = 8  # 8%

    # ✅ Festival boost (your calendar windows)
    fest_boost, fest_reasons = festival_boost(d)  # (percent, [label])

    increase_percent = normal_increase + int(fest_boost)
    predicted_price = float(base_price) * (1 + (increase_percent / 100.0))

    reasons = fest_reasons if fest_reasons else ["Normal demand"]

    return {
        "predicted_price": round(predicted_price, 2),
        "increase_percent": int(increase_percent),
        "reasons": reasons,
    }
