from __future__ import annotations


def predict_delay(duration):
    """
    Backward compatibility kosam simple function.
    Duration basis meeda rough delay estimate istundi.
    """
    try:
        duration = int(float(duration))
    except Exception:
        duration = 0

    if duration >= 180:
        return 20
    if duration >= 120:
        return 12
    if duration >= 60:
        return 5
    return 0


def predict_delay_minutes(*, airline: str, origin: str, destination: str, distance: float, dep_time: str) -> int:
    """
    Some flights ki maatrame realistic-like delay estimate chestundi.
    All flights ki kaadu.
    """
    try:
        hh = int(str(dep_time).split(":")[0])
    except Exception:
        hh = 12

    delay = 0

    # Peak hours
    if 7 <= hh <= 10 or 17 <= hh <= 21:
        delay += 15

    # Distance based
    try:
        distance = float(distance)
        if distance >= 1200:
            delay += 12
        elif distance >= 700:
            delay += 8
        elif distance >= 400:
            delay += 4
    except Exception:
        pass

    # Airline based
    airline_name = (airline or "").lower()
    if "air india" in airline_name:
        delay += 8
    elif "spice" in airline_name:
        delay += 6
    elif "indigo" in airline_name:
        delay += 4
    elif "vistara" in airline_name:
        delay += 3

    # Low-score flights ki alert ravakudadhu
    if delay < 18:
        return 0

    return int(delay)