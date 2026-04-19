from decimal import Decimal
import uuid

from django.db import models
from django.conf import settings
from django.utils import timezone

from flights.models import Flight


class Booking(models.Model):
    STATUS_CHOICES = (
        ("confirmed", "CONFIRMED"),
        ("pending", "PENDING"),
        ("cancelled", "CANCELLED"),
    )

    REFUND_STATUS_CHOICES = (
        ("not_applicable", "Not Applicable"),
        ("pending", "Pending"),
        ("processed", "Processed"),
        ("failed", "Failed"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    flight = models.ForeignKey(Flight, on_delete=models.CASCADE)

    passenger_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, default="MALE")
    email = models.EmailField()
    mobile = models.CharField(max_length=20)

    # ✅ Seat selected for this booking (store for quick display on ticket)
    seat_no = models.CharField(max_length=6, blank=True, default="")

    charges = models.FloatField(default=100)
    total_fare = models.FloatField(default=0)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="confirmed"
    )

    refund_status = models.CharField(
        max_length=20,
        choices=REFUND_STATUS_CHOICES,
        default="not_applicable",
    )
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    refund_requested_at = models.DateTimeField(null=True, blank=True)
    refund_processed_at = models.DateTimeField(null=True, blank=True)
    refund_ref_id = models.CharField(max_length=64, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    def calc_refund_amount(self) -> Decimal:
        fare = Decimal(str(self.total_fare or 0))
        return (fare * Decimal("0.80")).quantize(Decimal("0.01"))

    def initiate_refund(self):
        self.refund_status = "pending"
        self.refund_amount = self.calc_refund_amount()
        self.refund_requested_at = timezone.now()
        if not self.refund_ref_id:
            self.refund_ref_id = f"RF-{uuid.uuid4().hex[:10].upper()}"

    def save(self, *args, **kwargs):
        if self.flight_id:
            self.total_fare = float(self.flight.price) + float(self.charges)
        else:
            self.total_fare = float(self.charges)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Booking #{self.id} - {self.passenger_name}"


class Seat(models.Model):
    STATUS_CHOICES = (
        ("available", "AVAILABLE"),
        ("reserved", "RESERVED"),
        ("booked", "BOOKED"),
    )

    flight = models.ForeignKey("flights.Flight", on_delete=models.CASCADE, related_name="seats_map")
    seat_code = models.CharField(max_length=6)

    # final booking link (booked seat)
    booking = models.OneToOneField(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="seat",
    )

    # ✅ reservation (temporary lock)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="available")
    reserved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reserved_seats",
    )
    reserved_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("flight", "seat_code")

    def is_reserved_active(self):
        return self.status == "reserved" and self.reserved_until and self.reserved_until > timezone.now()

    def __str__(self):
        return f"{self.flight_id} - {self.seat_code}"
    
class HotelBooking(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    destination_slug = models.CharField(max_length=50)
    destination_code = models.CharField(max_length=10, blank=True)

    hotel_name = models.CharField(max_length=200)
    hotel_city = models.CharField(max_length=120, blank=True)
    price_per_night = models.FloatField(default=0)

    checkin_date = models.DateField()
    checkout_date = models.DateField()
    rooms = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def nights(self):
        return max((self.checkout_date - self.checkin_date).days, 1)

    @property
    def total_price(self):
        return self.nights * self.rooms * float(self.price_per_night or 0)

    def __str__(self):
        return f"{self.user} - {self.hotel_name} ({self.checkin_date} to {self.checkout_date})"