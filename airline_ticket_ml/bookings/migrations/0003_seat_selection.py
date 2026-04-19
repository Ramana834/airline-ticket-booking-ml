# Generated manually for seat selection feature

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0002_booking_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="seat_no",
            field=models.CharField(blank=True, default="", max_length=6),
        ),
        migrations.CreateModel(
            name="Seat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("seat_code", models.CharField(max_length=6)),
                (
                    "booking",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="seat",
                        to="bookings.booking",
                    ),
                ),
                (
                    "flight",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seats_map",
                        to="flights.flight",
                    ),
                ),
            ],
            options={
                "unique_together": {("flight", "seat_code")},
            },
        ),
    ]
