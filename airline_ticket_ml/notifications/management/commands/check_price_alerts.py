from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.models import PriceAlert, Notification
from ml_models.price_prediction import predict_price_trend


class Command(BaseCommand):
    help = "Check price alerts and create notifications if price drops."

    def handle(self, *args, **kwargs):
        alerts = PriceAlert.objects.filter(is_active=True)
        created = 0

        for alert in alerts:
            try:
                trend, confidence, sample_price = predict_price_trend(
                    alert.origin, alert.destination, str(alert.depart_date)
                )

                if sample_price is None:
                    continue

                # ✅ Trigger: current price <= target price
                if sample_price <= alert.target_price:
                    msg = (
                        f"Good news! Fare dropped for {alert.origin} → {alert.destination} "
                        f"on {alert.depart_date}. Current price: ₹{sample_price}"
                    )

                    # ✅ avoid spam (one per day for same route)
                    already = Notification.objects.filter(
                        user=alert.user,
                        title="Price Drop Alert",
                        message=msg,
                        created_at__date=timezone.now().date(),
                    ).exists()

                    if not already:
                        Notification.objects.create(
                            user=alert.user,
                            title="Price Drop Alert",
                            message=msg,
                        )
                        created += 1

                    alert.last_notified_at = timezone.now()
                    alert.save(update_fields=["last_notified_at"])

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error for alert {alert.id}: {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"✅ Checked {alerts.count()} alerts, created {created} notifications"
        ))
