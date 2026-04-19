from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from flights.models import Flight
from ml_models.delay_prediction import predict_delay_minutes
from .models import Notification, PriceAlert
from .predictor import predict_price


@dataclass
class AlertCheckResult:
    alert_id: int
    matched: bool
    current_min_price: float | None
    target_price: float | None
    notified: bool


CITY_CODE_MAP = {
    "hyderabad": "HYD",
    "hyderbad": "HYD",
    "delhi": "DEL",
    "mumbai": "BOM",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "chennai": "MAA",
}


def _parse_date(s):
    if not s:
        return None
    if hasattr(s, "year"):
        return s
    try:
        return datetime.strptime(str(s), "%Y-%m-%d").date()
    except Exception:
        return None


def _ensure_target_price(alert: PriceAlert, current_min: float | None) -> float | None:
    try:
        tp = float(alert.target_price) if alert.target_price is not None else None
        if tp is not None and tp > 0:
            return tp
    except Exception:
        pass

    if current_min is None:
        return None

    pred = predict_price(base_price=current_min, depart_date=alert.depart_date)
    expected = float(pred.get("predicted_price") or current_min)

    drop = max(int(alert.threshold_percent or 0), 0)
    if drop <= 0:
        return round(expected, 2)

    target = expected * (1 - (drop / 100.0))
    return round(target, 2)


def _find_matching_flight(origin: str, dest: str, d=None):
    """
    Safe matching:
    - source/source_code
    - destination/destination_code
    """
    qs = Flight.objects.filter(
        Q(source__iexact=origin) | Q(source_code__iexact=origin),
        Q(destination__iexact=dest) | Q(destination_code__iexact=dest),
    )

    if d:
        qs = qs.filter(date=d)

    return qs.order_by("price").first()


def check_price_alerts_for_user(user, limit=None) -> list[AlertCheckResult]:
    alerts_qs = PriceAlert.objects.filter(is_active=True, user=user).order_by("id")

    if limit:
        try:
            alerts_qs = alerts_qs[: int(limit)]
        except Exception:
            pass

    results: list[AlertCheckResult] = []

    for alert in alerts_qs:
        origin_raw = (alert.origin or "").strip().lower()
        dest_raw = (alert.destination or "").strip().lower()

        origin = CITY_CODE_MAP.get(origin_raw, origin_raw.upper())
        dest = CITY_CODE_MAP.get(dest_raw, dest_raw.upper())

        d = _parse_date(getattr(alert, "depart_date", None))

        flight = _find_matching_flight(origin, dest, d)
        current_min = float(flight.price) if flight else None

        target = _ensure_target_price(alert, current_min)

        matched = False
        notified = False

        if flight and target is not None and float(flight.price) <= float(target):
            matched = True

            already_sent_today = False
            if alert.last_notified_at:
                try:
                    already_sent_today = alert.last_notified_at.date() == timezone.localdate()
                except Exception:
                    already_sent_today = False

            if not already_sent_today:
                notif_origin = (
                    getattr(flight, "source_code", "")
                    or getattr(flight, "source", "")
                    or ""
                ).strip().upper()

                notif_dest = (
                    getattr(flight, "destination_code", "")
                    or getattr(flight, "destination", "")
                    or ""
                ).strip().upper()

                Notification.objects.create(
                    user=alert.user,
                    title="Price Drop Alert ✈️",
                    message=(
                        f"Price dropped! {notif_origin} → {notif_dest} "
                        f"on {flight.date} now ₹{flight.price} (Target ₹{target})"
                    ),
                    category="price",
                    origin=notif_origin,
                    destination=notif_dest,
                    depart_date=str(flight.date),
                    seat_class=(alert.seat_class or "economy"),
                )

                try:
                    if alert.user and getattr(alert.user, "email", ""):
                        send_mail(
                            subject="Flight Price Drop Alert ✈️",
                            message=(
                                f"Price dropped for {notif_origin} → {notif_dest} on {flight.date}.\n"
                                f"Current: ₹{flight.price}\nTarget: ₹{target}"
                            ),
                            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@flight.local"),
                            recipient_list=[alert.user.email],
                            fail_silently=True,
                        )
                except Exception:
                    pass

                notified = True
                alert.last_notified_at = timezone.now()

            alert.is_active = False
            alert.save()

        results.append(
            AlertCheckResult(
                alert_id=alert.id,
                matched=matched,
                current_min_price=current_min,
                target_price=target,
                notified=notified,
            )
        )

    return results


def approx_distance_km_from_duration(duration_value):
    try:
        duration_str = str(duration_value).strip().lower()

        if ":" in duration_str:
            hh, mm = duration_str.split(":")
            total_minutes = int(hh) * 60 + int(mm)
        else:
            total_minutes = int(float(duration_str))

        if total_minutes <= 0:
            return 300

        return max(300, int(total_minutes * 7.5))
    except Exception:
        return 500


def create_delay_notification_for_flight(user, flight, seat_class="economy", threshold=20) -> int:
    """
    Booked flight ki maatrame delay notification create chestundi.
    Some flights only.
    """
    if not user or not flight:
        return 0

    origin = (
        getattr(flight, "source_code", "")
        or getattr(flight, "source", "")
        or ""
    ).strip().upper()

    destination = (
        getattr(flight, "destination_code", "")
        or getattr(flight, "destination", "")
        or ""
    ).strip().upper()

    depart_date = str(getattr(flight, "date", "") or "")
    dep_time = str(getattr(flight, "departure_time", "") or "12:00")
    airline = getattr(flight, "airline", "") or ""
    flight_no = getattr(flight, "flight_no", "") or getattr(flight, "flight_number", "") or ""

    already_exists = Notification.objects.filter(
        user=user,
        category="delay",
        origin=origin,
        destination=destination,
        depart_date=depart_date,
    ).exists()

    if already_exists:
        return 0

    distance_km = approx_distance_km_from_duration(getattr(flight, "duration", 0))

    predicted_delay = predict_delay_minutes(
        airline=airline,
        origin=origin,
        destination=destination,
        distance=float(distance_km),
        dep_time=dep_time,
    )

    if int(predicted_delay) < int(threshold):
        return 0

    Notification.objects.create(
        user=user,
        title="Delay Alert ⏰",
        message=(
            f"Your booked flight may be delayed.\n"
            f"{origin} → {destination} on {depart_date}\n"
            f"Airline: {airline} ({flight_no})\n"
            f"Departure: {dep_time}\n"
            f"Predicted delay: {int(predicted_delay)} minutes"
        ),
        category="delay",
        origin=origin,
        destination=destination,
        depart_date=depart_date,
        seat_class=(seat_class or "economy"),
    )

    return int(predicted_delay)