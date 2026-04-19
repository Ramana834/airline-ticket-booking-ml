# flights/management/commands/load_flights.py
import csv
import os
from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from flights.models import Flight


def to_int(v, default=0):
    try:
        return int(float(str(v).strip()))
    except Exception:
        return default


def duration_to_minutes(dur):
    s = (dur or "").strip()
    if not s:
        return 0
    if ":" in s:
        try:
            h, m = s.split(":")
            return int(h) * 60 + int(m)
        except Exception:
            return 0
    return to_int(s, 0)


def pick(row, *keys, default=""):
    for k in keys:
        v = row.get(k)
        if v is None:
            continue
        v = str(v).strip()
        if v != "":
            return v
    return default


def norm_code(x):
    return (x or "").strip().upper()


class Command(BaseCommand):
    help = "Load domestic + international flights, generate next 180 days DAILY, remove duplicates"

    def handle(self, *args, **kwargs):
        DAYS = 180
        today = date.today()
        end_date = today + timedelta(days=DAYS)
        BULK_CHUNK = 15000

        data_dir = os.path.join(settings.BASE_DIR, "Data")
        files = ["domestic_flights.csv", "international_flights.csv"]

        self.stdout.write(self.style.WARNING("Deleting old flights..."))
        Flight.objects.all().delete()

        total_created = 0
        buffer = []
        skipped = 0
        read_rows = 0

        # ✅ duplicates key (route + date + time + flight_no)
        seen = set()

        def flush():
            nonlocal total_created, buffer
            if not buffer:
                return
            Flight.objects.bulk_create(buffer, batch_size=BULK_CHUNK)
            total_created += len(buffer)
            buffer = []
            self.stdout.write(self.style.SUCCESS(f"Inserted: {total_created} flights"))

        self.stdout.write(
            self.style.SUCCESS(f"Generating DAILY flights for {DAYS} days: {today} → {end_date}")
        )

        with transaction.atomic():
            for name in files:
                file_path = os.path.join(data_dir, name)
                if not os.path.exists(file_path):
                    self.stdout.write(self.style.ERROR(f"File not found: {file_path}"))
                    continue

                self.stdout.write(self.style.SUCCESS(f"Reading: {file_path}"))

                with open(file_path, "r", encoding="utf-8", errors="ignore", newline="") as f:
                    reader = csv.DictReader(f)

                    for row in reader:
                        read_rows += 1

                        airline = pick(row, "airline", "Airline")
                        flight_no = pick(row, "flight_no", "flight", "FlightNo", default="")

                        source_code = norm_code(pick(row, "origin", "source", "from"))
                        dest_code = norm_code(pick(row, "destination", "dest", "to"))

                        dep_time = pick(row, "depart_time", "departure_time", "depart")
                        arr_time = pick(row, "arrival_time", "arrive_time", "arrive")

                        duration = duration_to_minutes(pick(row, "duration", default=""))

                        eco = to_int(pick(row, "economy_fare", "price", "fare", default="0"), 0)
                        bus = to_int(pick(row, "business_fare", default="0"), 0)
                        fst = to_int(pick(row, "first_fare", default="0"), 0)

                        # ✅ If dataset doesn't provide class fares, derive them from economy
                        if eco and not bus:
                            bus = int(round(eco * 1.6))
                        if eco and not fst:
                            fst = int(round(eco * 2.2))

                        # ✅ minimal required fields
                        if not (source_code and dest_code and dep_time and arr_time):
                            skipped += 1
                            continue

                        d = today
                        while d <= end_date:
                            key = (
                                source_code,
                                dest_code,
                                str(d),
                                str(dep_time).strip(),
                                str(flight_no).strip().upper(),
                            )

                            if key not in seen:
                                seen.add(key)

                                buffer.append(
                                    Flight(
                                        airline=airline,
                                        flight_no=flight_no,
                                        source_code=source_code,
                                        destination_code=dest_code,
                                        source=source_code,
                                        destination=dest_code,
                                        departure_time=dep_time,
                                        arrival_time=arr_time,
                                        duration=duration,
                                        price=eco,  # keep compatibility
                                        economy_fare=eco,
                                        business_fare=bus,
                                        first_fare=fst,
                                        seats=180,
                                        date=d,
                                    )
                                )

                                if len(buffer) >= BULK_CHUNK:
                                    flush()

                            # ✅ always increment day (even if duplicate)
                            d += timedelta(days=1)

            flush()

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ DONE. Total flights created: {total_created} | Read rows: {read_rows} | Skipped: {skipped}"
            )
        )