from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
import re

User = get_user_model()


class PriceAlert(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    origin = models.CharField(max_length=20)
    destination = models.CharField(max_length=20)
    depart_date = models.CharField(max_length=20)
    seat_class = models.CharField(max_length=30, default="economy")

    threshold_percent = models.IntegerField(default=15)
    is_active = models.BooleanField(default=True)

    target_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_notified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} {self.origin}->{self.destination} {self.depart_date} (+{self.threshold_percent}%)"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    title = models.CharField(max_length=200)
    message = models.TextField()

    origin = models.CharField(max_length=20, blank=True, default="")
    destination = models.CharField(max_length=20, blank=True, default="")
    depart_date = models.CharField(max_length=20, blank=True, default="")
    seat_class = models.CharField(max_length=30, blank=True, default="economy")

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    category = models.CharField(max_length=30, default="general")

    def __str__(self):
        return f"{self.user} - {self.title}"

    @property
    def booking_url(self) -> str:
        o = (self.origin or "").strip().upper()
        d = (self.destination or "").strip().upper()
        dt = (self.depart_date or "").strip()
        sc = (self.seat_class or "economy").strip().lower()

        if not (o and d and dt):
            msg = self.message or ""
            m = re.search(r"([A-Z]{3,20})\s*→\s*([A-Z]{3,20}).*?on\s*(\d{4}-\d{2}-\d{2})", msg)
            if m:
                o, d, dt = m.group(1), m.group(2), m.group(3)

        if not (o and d and dt):
            return ""

        return f"/results/?TripType=1&Origin={o}&Destination={d}&DepartDate={dt}&SeatClass={sc}"