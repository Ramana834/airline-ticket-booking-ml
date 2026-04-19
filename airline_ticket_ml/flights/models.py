# flights/models.py
from django.db import models

class Flight(models.Model):
    airline = models.CharField(max_length=100)
    flight_no = models.CharField(max_length=20, blank=True, default="")

    source_code = models.CharField(max_length=10, default="", blank=True)
    destination_code = models.CharField(max_length=10, default="", blank=True)
    source = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)

    departure_time = models.CharField(max_length=10)
    arrival_time = models.CharField(max_length=10)
    duration = models.IntegerField()

    # ✅ keep price as economy (for compatibility)
    price = models.IntegerField()

    # ✅ add these (from CSV)
    economy_fare = models.IntegerField(default=0)
    business_fare = models.IntegerField(default=0)
    first_fare = models.IntegerField(default=0)

    seats = models.IntegerField(default=180)
    date = models.DateField()

    def fare_for(self, seat_class: str) -> int:
        sc = (seat_class or "economy").strip().lower()
        if sc == "business":
            return int(self.business_fare or self.price or 0)
        if sc in ["first", "first class", "firstclass"]:
            return int(self.first_fare or self.price or 0)
        return int(self.economy_fare or self.price or 0)