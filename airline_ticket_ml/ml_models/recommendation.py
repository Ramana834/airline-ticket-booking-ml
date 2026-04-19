from __future__ import annotations

from typing import Iterable, List

from django.db.models import Count
from flights.models import Flight


def recommend(user_id: int):
    """Legacy helper (kept)."""
    return []


def recommend_flights(user, recent_bookings=None, limit: int = 10) -> List[Flight]:
    """
    Smart Flight Recommendations (rule-based baseline):
    - learns preferred airline and destinations from recent bookings
    - recommends upcoming flights matching those preferences
    """
    preferred_airline = None
    preferred_dest = None

    if recent_bookings:
        # airline preference
        airline_counts = {}
        dest_counts = {}
        for b in recent_bookings:
            if not getattr(b, "flight", None):
                continue
            airline_counts[b.flight.airline] = airline_counts.get(b.flight.airline, 0) + 1
            dest_counts[b.flight.destination] = dest_counts.get(b.flight.destination, 0) + 1

        if airline_counts:
            preferred_airline = max(airline_counts, key=airline_counts.get)
        if dest_counts:
            preferred_dest = max(dest_counts, key=dest_counts.get)

    qs = Flight.objects.all().order_by("date", "departure_time")

    if preferred_airline:
        qs = qs.filter(airline=preferred_airline)

    if preferred_dest:
        qs = qs.filter(destination=preferred_dest)

    return list(qs[:limit])
