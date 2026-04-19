from __future__ import annotations

from datetime import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils.dateparse import parse_date

from flights.models import Flight
from bookings.models import Booking
from notifications.models import PriceAlert

from ml_models.price_prediction import predict_price_trend
from ml_models.recommendation import recommend_flights
from ml_models.delay_prediction import predict_delay_minutes


@login_required
def fare_trend(request):
    origin = (request.GET.get("origin") or "").strip().upper()
    destination = (request.GET.get("destination") or "").strip().upper()
    depart_date_str = (request.GET.get("date") or "").strip()

    trend = None
    confidence = None
    sample_price = None

    set_alert = False
    active_alert = None

    # ✅ parse date safely (supports YYYY-MM-DD)
    depart_date_obj = parse_date(depart_date_str) if depart_date_str else None

    if origin and destination and depart_date_obj:
        trend, confidence, sample_price = predict_price_trend(origin, destination, depart_date_str)

        # ✅ user clicked Create Alert
        if request.GET.get("set_alert") == "1":
            alert, created = PriceAlert.objects.get_or_create(
                user=request.user,
                origin=origin,
                destination=destination,
                depart_date=depart_date_obj,  # ✅ DateField safe
                defaults={
                    "target_price": float(sample_price or 0),
                    "is_active": True,
                },
            )

            # If already exists but inactive, reactivate
            if not created and hasattr(alert, "is_active") and not alert.is_active:
                alert.is_active = True
                if hasattr(alert, "target_price") and (alert.target_price is None or alert.target_price == 0):
                    alert.target_price = float(sample_price or 0)
                alert.save(update_fields=["is_active", "target_price"])
                created = True

            if created:
                messages.success(request, "Price alert created. We'll notify you if price drops.")
            else:
                messages.info(request, "Price alert is already active for this route/date.")

            set_alert = True
            active_alert = alert

        else:
            # show status if alert already exists (even if not clicked now)
            active_alert = (
                PriceAlert.objects.filter(
                    user=request.user,
                    origin=origin,
                    destination=destination,
                    depart_date=depart_date_obj,
                )
                .order_by("-id")
                .first()
            )
            if active_alert and getattr(active_alert, "is_active", True):
                set_alert = True

    elif (origin or destination or depart_date_str):
        # user typed something but not valid
        if not depart_date_obj:
            messages.error(request, "Please select a valid date.")
        else:
            messages.error(request, "Please enter Origin and Destination.")

    context = {
        "origin": origin,
        "destination": destination,
        "depart_date": depart_date_str,   # template uses this
        "trend": trend,
        "confidence": confidence,
        "sample_price": sample_price,
        "set_alert": set_alert,           # ✅ IMPORTANT for your template button
        "active_alert": active_alert,
    }
    return render(request, "ml_features/fare_trend.html", context)


@login_required
def recommendations(request):
    # Use user's bookings/search history for personalization
    recent_bookings = Booking.objects.filter(user=request.user).select_related("flight").order_by("-created_at")[:10]
    recs = recommend_flights(user=request.user, recent_bookings=recent_bookings)

    return render(request, "ml_features/recommendations.html", {"recs": recs, "recent_bookings": recent_bookings})


@login_required
def delay_prediction(request):
    prediction = None
    if request.method == "POST":
        airline = request.POST.get("airline", "")
        origin = request.POST.get("origin", "")
        destination = request.POST.get("destination", "")
        distance = request.POST.get("distance", "")
        dep_time = request.POST.get("dep_time", "")

        try:
            distance_val = float(distance)
            prediction = predict_delay_minutes(
                airline=airline,
                origin=origin,
                destination=destination,
                distance=distance_val,
                dep_time=dep_time,
            )
        except Exception as e:
            messages.error(request, f"Could not predict delay: {e}")

    # Provide dropdown values from DB
    airlines = Flight.objects.values_list("airline", flat=True).distinct().order_by("airline")
    airports = Flight.objects.values_list("source", flat=True).distinct().order_by("source")

    return render(
        request,
        "ml_features/delay.html",
        {"prediction": prediction, "airlines": airlines, "airports": airports},
    )


@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        messages.error(request, "Admin dashboard is available for staff users only.")
        return redirect("flights:home")

    # KPI cards
    total_bookings = Booking.objects.count()
    confirmed = Booking.objects.filter(status="confirmed").count()
    cancelled = Booking.objects.filter(status="cancelled").count()
    revenue = (
        Booking.objects.filter(status="confirmed").aggregate(s=Sum("total_fare")).get("s")
        or 0
    )

    # Charts data
    top_routes = (
        Booking.objects.filter(status="confirmed")
        .values("flight__source", "flight__destination")
        .annotate(c=Count("id"))
        .order_by("-c")[:7]
    )

    top_airlines = (
        Booking.objects.filter(status="confirmed")
        .values("flight__airline")
        .annotate(c=Count("id"))
        .order_by("-c")[:7]
    )

    rev_by_month = (
        Booking.objects.filter(status="confirmed")
        .annotate(m=TruncMonth("created_at"))
        .values("m")
        .annotate(s=Sum("total_fare"))
        .order_by("m")
    )
    # ✅ Refund analytics
    total_refunded = Booking.objects.filter(
        refund_status="processed"
    ).aggregate(total=Sum("refund_amount"))


    return render(
        request,
        "ml_features/admin_dashboard.html",
        {
            "total_refunded": total_refunded,
            "total_bookings": total_bookings,
            "confirmed": confirmed,
            "cancelled": cancelled,
            "revenue": float(revenue),
            "top_routes": list(top_routes),
            "top_airlines": list(top_airlines),
            "rev_by_month": [
                {"month": x["m"].strftime("%b %Y") if x["m"] else "-", "revenue": float(x["s"] or 0)}
                for x in rev_by_month
            ],
        },
    )


@login_required
def chatbot(request):
    """A simple in-app assistant (rule-based) using your existing ML helpers."""
    if request.method == "GET":
        return render(request, "ml_features/chatbot.html")

    msg = (request.POST.get("message") or "").strip().lower()
    if not msg:
        return JsonResponse({"reply": "Tell me what you want: cheap flights, fare trend, delay, etc."})

    # Very small intent detection
    if "delay" in msg:
        return JsonResponse({"reply": "Open Delay Prediction page and enter flight details. I’ll estimate delay minutes."})

    if "trend" in msg or "best time" in msg or "price" in msg:
        return JsonResponse({"reply": "Try Fare Trend page. It shows whether price may increase and confidence."})

    if "cheap" in msg or "recommend" in msg or "suggest" in msg:
        recent_bookings = Booking.objects.filter(user=request.user).select_related("flight").order_by("-created_at")[:10]
        recs = recommend_flights(user=request.user, recent_bookings=recent_bookings)[:3]
        if not recs:
            return JsonResponse({"reply": "No recommendations found yet. Make one booking/search first."})
        lines = []
        for r in recs:
            # rec can be dict or model depending on your ml function
            airline = getattr(r, "airline", None) or (r.get("airline") if isinstance(r, dict) else "")
            src = getattr(r, "source", None) or (r.get("source") if isinstance(r, dict) else "")
            dst = getattr(r, "destination", None) or (r.get("destination") if isinstance(r, dict) else "")
            price = getattr(r, "price", None) or (r.get("price") if isinstance(r, dict) else "")
            lines.append(f"• {airline} {src}→{dst} ₹{price}")
        return JsonResponse({"reply": "Here are some cheap suggestions:\n" + "\n".join(lines)})

    return JsonResponse({"reply": "I can help with: cheap recommendations, fare trend, delay prediction, tickets."})
