import random
from datetime import timedelta

from flights.models import Flight


def _rand_time_slots():
    dep_candidates = ["05:30", "07:15", "09:00", "11:40", "14:10", "16:30", "19:05", "22:20"]
    dep = random.choice(dep_candidates)

    dur = random.choice([120, 150, 180, 240, 300, 420, 540, 720, 900])
    h, m = map(int, dep.split(":"))
    dep_minutes = h * 60 + m
    arr_minutes = (dep_minutes + dur) % (24 * 60)
    arr = f"{arr_minutes//60:02d}:{arr_minutes%60:02d}"
    return dep, arr, dur


def ensure_route_flights(source, destination, depart_date, n=10):
    airlines = ["Indigo", "AirIndia", "SpiceJet", "Vistara", "Emirates", "Qatar", "Lufthansa", "KLM"]
    prefixes = ["AI", "6E", "SG", "UK", "EK", "QR", "LH", "KL"]

    created = 0
    for _ in range(n):
        dep, arr, dur = _rand_time_slots()
        eco = int(2500 + dur * 12 + random.randint(0, 1500))
        bus = int(eco * 1.8)
        fst = int(eco * 2.6)
        flight_no = f"{random.choice(prefixes)}{random.randint(100, 9999)}"

        # avoid duplicates for same day
        if Flight.objects.filter(
            source=source, destination=destination, date=depart_date,
            departure_time=dep
        ).exists():
            continue

        Flight.objects.create(
            airline=random.choice(airlines),
            flight_no=flight_no,
            source_code=source,
            destination_code=destination,
            source=source,
            destination=destination,
            departure_time=dep,
            arrival_time=arr,
            duration=dur,
            price=eco,
            economy_fare=eco,
            business_fare=bus,
            first_fare=fst,
            seats=180,
            date=depart_date
        )
        created += 1

    return created