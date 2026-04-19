from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone

from .models import PriceAlert, Notification
from .services import check_price_alerts_for_user


@login_required
def my_notifications(request):
    alerts = PriceAlert.objects.filter(user=request.user).order_by("-created_at")
    notifications = Notification.objects.filter(user=request.user).order_by("-created_at")
    unread_count = notifications.filter(is_read=False).count()

    return render(request, "notifications/notifications.html", {
        "alerts": alerts,
        "notifications": notifications,
        "unread_count": unread_count,
    })


@login_required
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect("notifications:my_notifications")


@login_required
def mark_notification_read(request, pk):
    item = get_object_or_404(Notification, pk=pk, user=request.user)
    if not item.is_read:
        item.is_read = True
        item.save(update_fields=["is_read"])

    if getattr(item, "booking_url", ""):
        return redirect(item.booking_url)

    return redirect("notifications:my_notifications")


@login_required
def unread_count(request):
    c = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({"count": c})


@login_required
def latest_unread(request):
    n = Notification.objects.filter(user=request.user, is_read=False).order_by("-created_at").first()
    if not n:
        return JsonResponse({"has": False})

    return JsonResponse({
        "has": True,
        "id": n.id,
        "title": n.title,
        "message": n.message,
        "category": n.category,
        "created_at": timezone.localtime(n.created_at).strftime("%d %b %Y, %I:%M %p"),
        "booking_url": getattr(n, "booking_url", ""),
    })


@login_required
def create_price_alert(request):
    if request.method != "POST":
        return redirect("flights:home")

    origin = (request.POST.get("origin") or "").strip().upper()
    destination = (request.POST.get("destination") or "").strip().upper()
    depart_date = (request.POST.get("depart_date") or "").strip()
    seat_class = (request.POST.get("seat_class") or "economy").strip().lower()

    try:
        threshold_percent = int(request.POST.get("threshold_percent") or 15)
    except ValueError:
        threshold_percent = 15

    target_price_raw = (request.POST.get("target_price") or "").strip()

    target_price = None
    if target_price_raw:
        try:
            tp = Decimal(target_price_raw)
            if tp > 0:
                target_price = tp
        except (InvalidOperation, ValueError):
            target_price = None

    if not origin or not destination or not depart_date:
        messages.error(request, "Alert create failed: missing route/date.")
        return redirect("flights:home")

    PriceAlert.objects.update_or_create(
        user=request.user,
        origin=origin,
        destination=destination,
        depart_date=depart_date,
        seat_class=seat_class,
        defaults={
            "threshold_percent": threshold_percent,
            "is_active": True,
            "target_price": target_price,
        }
    )

    if target_price is not None:
        messages.success(
            request,
            f"Price alert set: {origin} → {destination} (Target ₹{int(target_price)})."
        )
    else:
        messages.success(
            request,
            f"Price alert set: {origin} → {destination} (Drop {threshold_percent}% below expected)."
        )

    return redirect("notifications:my_notifications")


@login_required
def check_now(request):
    results = check_price_alerts_for_user(request.user)
    created = sum(1 for r in results if getattr(r, "notified", False))

    if created:
        messages.success(request, f"✅ Checked alerts. New notifications: {created}")
    else:
        messages.info(request, "Checked alerts. No price drop notifications yet.")

    return redirect("notifications:my_notifications")