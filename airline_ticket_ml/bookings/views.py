# bookings/views.py

from datetime import datetime, timedelta
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from flights.models import Flight
from notifications.services import create_delay_notification_for_flight
from .models import Booking, Seat, HotelBooking

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


# =========================
# HELPERS
# =========================
def _safe_code(text, default="XXX"):
    text = (text or "").strip()
    return text[:3].upper() if text else default


def class_multiplier(seat_class):
    seat_class = (seat_class or "").strip().lower()
    if seat_class == "business":
        return 1.5
    if seat_class in ["first", "first class", "firstclass"]:
        return 2.2
    return 1.0


def fmt_time(t):
    if t is None:
        return ""
    if hasattr(t, "strftime"):
        return t.strftime("%H:%M")

    t = str(t).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(t, fmt).strftime("%H:%M")
        except ValueError:
            pass
    return t


def fmt_date(d):
    if d is None:
        return ""
    if hasattr(d, "strftime"):
        return d.strftime("%d %b %Y")

    d = str(d).strip()
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return d


def parse_hhmm_to_time(t: str):
    t = (t or "").strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(t, fmt).time()
        except Exception:
            pass
    return None


def is_departure_in_past(flight: Flight) -> bool:
    """
    Block booking past flights:
    - if flight.date < today => past
    - if flight.date == today and departure_time <= now => already departed
    """
    try:
        if not flight or not getattr(flight, "date", None):
            return False

        today = timezone.localdate()

        if flight.date < today:
            return True

        if flight.date > today:
            return False

        ft = parse_hhmm_to_time(getattr(flight, "departure_time", "") or "")
        if not ft:
            return False

        now_t = timezone.localtime().time()
        return ft <= now_t
    except Exception:
        return False


def _digits_only(s: str) -> str:
    return "".join([c for c in (s or "") if c.isdigit()])


def safe_duration_text(flight: Flight) -> str:
    d = getattr(flight, "duration", None)
    try:
        if d is None or d == "":
            return "—"
        d = int(float(d))
        return f"{d//60}h {d%60}m"
    except Exception:
        return "—"


# =========================
# BOOKINGS LIST / HISTORY
# =========================
@login_required
def my_bookings(request):
    bookings = (
        Booking.objects.filter(user=request.user)
        .select_related("flight")
        .order_by("-created_at")
    )
    return render(request, "bookings/my_bookings.html", {"bookings": bookings})


@login_required
def history(request):
    return redirect("bookings:my_bookings")


# =========================
# REVIEW
# =========================
@login_required
def review(request, flight_id):
    outbound = get_object_or_404(Flight, id=flight_id)

    request.session["outbound_flight_id"] = outbound.id
    request.session["flight_id"] = outbound.id

    if is_departure_in_past(outbound):
        messages.error(request, "This flight has already departed. Please choose another flight.")
        return redirect("flights:home")

    trip_type = str(request.session.get("trip_type", "1"))
    return_flight_id = request.session.get("return_flight_id")

    return_flight = None
    if trip_type == "2" and return_flight_id:
        return_flight = Flight.objects.filter(id=return_flight_id).first()

        if return_flight and str(return_flight.id) == str(outbound.id):
            request.session.pop("return_flight_id", None)
            return_flight = None

        if return_flight and is_departure_in_past(return_flight):
            messages.error(request, "Return flight has already departed. Please choose another return flight.")
            request.session.pop("return_flight_id", None)
            return redirect("flights:home")
    else:
        if trip_type != "2":
            request.session.pop("return_flight_id", None)

    seat_class = (request.GET.get("seat_class") or request.session.get("seat_class") or "economy").strip().lower()
    request.session["seat_class"] = seat_class

    outbound_base = float(outbound.fare_for(seat_class) or 0)
    return_base = float(return_flight.fare_for(seat_class) or 0) if return_flight else 0.0

    charges = 100.0
    total_one = (outbound_base + charges) + ((return_base + charges) if return_flight else 0.0)

    if request.method == "POST":
        request.session["country_code"] = (request.POST.get("country_code") or "+91").strip()
        request.session["mobile"] = _digits_only((request.POST.get("mobile") or "").strip())
        request.session["email"] = (request.POST.get("email") or "").strip()

        if len(request.session["mobile"]) != 10:
            messages.error(request, "Mobile number must be exactly 10 digits.")
            return redirect("bookings:review", flight_id=outbound.id)

        passenger_list = []
        gender_list = []

        i = 0
        while True:
            n = request.POST.get(f"passenger_name_{i}")
            g = request.POST.get(f"gender_{i}")
            if n is None and g is None:
                break
            n = (n or "").strip()
            g = (g or "MALE").strip().upper()
            if n:
                passenger_list.append(n)
                gender_list.append(g)
            i += 1

        if not passenger_list:
            names = request.POST.getlist("passenger_name") or request.POST.getlist("passenger_names")
            genders = request.POST.getlist("gender") or request.POST.getlist("genders")
            for idx, n in enumerate(names):
                n = (n or "").strip()
                if not n:
                    continue
                passenger_list.append(n)
                gender_list.append(((genders[idx] if idx < len(genders) else "MALE") or "MALE").strip().upper())

        if not passenger_list:
            messages.error(request, "Please add at least one passenger name.")
            return redirect("bookings:review", flight_id=outbound.id)

        request.session["passenger_list"] = passenger_list
        request.session["gender_list"] = gender_list
        request.session["seat_selection_done"] = False
        request.session["seat_assignments"] = {}

        return redirect("bookings:select_seat", flight_id=outbound.id)

    context = {
        "flight": {
            "airline": getattr(outbound, "airline", ""),
            "flight_no": getattr(outbound, "flight_no", "") or "",
            "depart": fmt_time(getattr(outbound, "departure_time", None)),
            "arrive": fmt_time(getattr(outbound, "arrival_time", None)),
        },
        "origin": getattr(outbound, "source", ""),
        "destination": getattr(outbound, "destination", ""),
        "depart_date": fmt_date(getattr(outbound, "date", None)),
        "origin_airport": "Airport Terminal",
        "dest_airport": "Airport Terminal",
        "duration": safe_duration_text(outbound),
        "baggage_text": "30 Kgs Check-in, 7 Kgs Cabin",
        "return_flight": None,
        "seat_class": seat_class,
        "outbound_base": round(outbound_base, 2),
        "return_base": round(return_base, 2),
        "charges": round(charges, 2),
        "total_fare": round(total_one, 2),
    }

    if return_flight:
        context["return_flight"] = {
            "airline": getattr(return_flight, "airline", ""),
            "flight_no": getattr(return_flight, "flight_no", "") or "",
            "depart": fmt_time(getattr(return_flight, "departure_time", None)),
            "arrive": fmt_time(getattr(return_flight, "arrival_time", None)),
            "depart_date": fmt_date(getattr(return_flight, "date", None)),
            "origin": getattr(return_flight, "source", ""),
            "destination": getattr(return_flight, "destination", ""),
        }

    return render(request, "flights/review.html", context)


# =========================
# SEAT SELECTION
# =========================
@login_required
def select_seat(request, flight_id):
    flight = get_object_or_404(Flight, id=flight_id)

    passenger_list = [p.strip() for p in (request.session.get("passenger_list") or []) if (p or "").strip()]
    if not passenger_list:
        passenger_list = ["Passenger"]

    rows = list(range(1, 11))
    cols = ["A", "B", "C", "D", "E", "F"]
    all_codes = [f"{r}{c}" for r in rows for c in cols]

    existing_codes = set(
        Seat.objects.filter(flight=flight, seat_code__in=all_codes).values_list("seat_code", flat=True)
    )
    to_create = [Seat(flight=flight, seat_code=code) for code in all_codes if code not in existing_codes]
    if to_create:
        Seat.objects.bulk_create(to_create, ignore_conflicts=True)

    Seat.objects.filter(
        flight=flight,
        status="reserved",
        reserved_until__lte=timezone.now()
    ).update(status="available", reserved_by=None, reserved_until=None)

    seats_qs = Seat.objects.filter(flight=flight, seat_code__in=all_codes).select_related("booking", "reserved_by")

    booked = {s.seat_code for s in seats_qs if s.booking_id or s.status == "booked"}

    reserved_other = {
        s.seat_code for s in seats_qs
        if s.status == "reserved" and s.reserved_until and s.reserved_until > timezone.now()
        and s.reserved_by_id != request.user.id
    }
    reserved_me = {
        s.seat_code for s in seats_qs
        if s.status == "reserved" and s.reserved_until and s.reserved_until > timezone.now()
        and s.reserved_by_id == request.user.id
    }

    if request.method == "POST":
        seat_assignments = {}
        chosen = []

        for i in range(len(passenger_list)):
            code = (request.POST.get(f"seat_{i}") or "").strip().upper()
            seat_assignments[str(i)] = code
            if code:
                chosen.append(code)

        if len(chosen) != len(passenger_list):
            messages.error(request, "Please select seats for all passengers.")
        elif len(set(chosen)) != len(chosen):
            messages.error(request, "Duplicate seats selected. Choose different seats.")
        else:
            hold_until = timezone.now() + timedelta(minutes=10)

            try:
                with transaction.atomic():
                    locked = list(
                        Seat.objects.select_for_update()
                        .filter(flight=flight, seat_code__in=chosen)
                    )

                    for s in locked:
                        if s.booking_id or s.status == "booked":
                            raise ValueError(f"Seat {s.seat_code} already booked.")

                        if (
                            s.status == "reserved"
                            and s.reserved_until
                            and s.reserved_until > timezone.now()
                            and s.reserved_by_id != request.user.id
                        ):
                            raise ValueError(f"Seat {s.seat_code} is reserved by another user.")

                    Seat.objects.filter(flight=flight, seat_code__in=chosen).update(
                        status="reserved",
                        reserved_by=request.user,
                        reserved_until=hold_until
                    )

                request.session["seat_assignments"] = seat_assignments
                request.session["seat_selection_done"] = True
                request.session["seat_hold_until"] = hold_until.isoformat()
                return redirect("bookings:payment")

            except Exception as e:
                messages.error(request, str(e))
                return redirect("bookings:select_seat", flight_id=flight.id)

    return render(request, "bookings/select_seat.html", {
        "flight": flight,
        "rows": rows,
        "cols": cols,
        "booked": booked,
        "reserved_other": reserved_other,
        "reserved_me": reserved_me,
        "passengers": list(enumerate(passenger_list)),
    })


@login_required
def seat_status_api(request, flight_id):
    flight = get_object_or_404(Flight, id=flight_id)

    Seat.objects.filter(
        flight=flight,
        status="reserved",
        reserved_until__lte=timezone.now()
    ).update(status="available", reserved_by=None, reserved_until=None)

    seats = Seat.objects.filter(flight=flight).values(
        "seat_code", "status", "booking_id", "reserved_by_id", "reserved_until"
    )

    data = []
    for s in seats:
        code = s["seat_code"]
        if s["booking_id"] or s["status"] == "booked":
            state = "booked"
        elif s["status"] == "reserved" and s["reserved_until"] and s["reserved_until"] > timezone.now():
            state = "reserved_me" if s["reserved_by_id"] == request.user.id else "reserved_other"
        else:
            state = "available"
        data.append({"seat": code, "state": state})

    return JsonResponse({"seats": data})


# =========================
# PAYMENT
# =========================
@login_required
def payment(request):
    outbound_id = request.session.get("outbound_flight_id") or request.session.get("flight_id")
    if not outbound_id:
        messages.error(request, "Outbound flight not found.")
        return redirect("flights:home")

    outbound = get_object_or_404(Flight, id=outbound_id)

    if is_departure_in_past(outbound):
        messages.error(request, "This flight has already departed. Please choose another flight.")
        return redirect("flights:home")

    return_id = request.session.get("return_flight_id")
    trip_type = str(request.session.get("trip_type", "1"))

    if return_id:
        trip_type = "2"
        request.session["trip_type"] = "2"

    return_flight = None
    if trip_type == "2" and return_id:
        return_flight = Flight.objects.filter(id=return_id).first()

    if return_flight and str(return_flight.id) == str(outbound.id):
        return_flight = None
        request.session.pop("return_flight_id", None)

    if return_flight and is_departure_in_past(return_flight):
        messages.error(request, "Return flight has already departed. Please choose another return flight.")
        request.session.pop("return_flight_id", None)
        return redirect("flights:home")

    seat_class = (request.session.get("seat_class") or "economy").strip().lower()

    outbound_base = float(outbound.fare_for(seat_class) or 0)
    return_base = float(return_flight.fare_for(seat_class) or 0) if return_flight else 0.0
    charges = 100.0

    passenger_list = [p.strip() for p in (request.session.get("passenger_list") or []) if (p or "").strip()]
    gender_list = [(g or "MALE").strip().upper() for g in (request.session.get("gender_list") or [])]

    if not passenger_list:
        passenger_list = ["Passenger"]
    if not gender_list:
        gender_list = ["MALE"]

    passenger_count = len(passenger_list)

    per_passenger_total = (outbound_base + charges) + ((return_base + charges) if return_flight else 0.0)
    total_amount = per_passenger_total * passenger_count

    month_range = [f"{i:02d}" for i in range(1, 13)]
    current_year = datetime.now().year
    year_range = list(range(current_year, current_year + 16))

    if not request.session.get("seat_selection_done"):
        messages.error(request, "Please select seats before payment.")
        return redirect("bookings:select_seat", flight_id=outbound.id)

    def _digits_only_local(v: str) -> str:
        return re.sub(r"\D", "", (v or ""))

    if request.method == "POST":
        card_number_raw = (request.POST.get("card_number") or "").strip()
        card_number = _digits_only_local(card_number_raw)

        cvv = _digits_only_local(request.POST.get("cvv"))
        exp_month = _digits_only_local(request.POST.get("exp_month"))
        exp_year = _digits_only_local(request.POST.get("exp_year"))
        card_name = (request.POST.get("card_name") or "").strip()

        if len(card_number) != 16:
            messages.error(request, "Card number must be exactly 16 digits.")
            return redirect("bookings:payment")

        if len(cvv) != 3:
            messages.error(request, "CVV must be exactly 3 digits.")
            return redirect("bookings:payment")

        if not exp_month.isdigit() or not (1 <= int(exp_month) <= 12):
            messages.error(request, "Invalid expiry month.")
            return redirect("bookings:payment")

        if not exp_year.isdigit() or len(exp_year) != 4:
            messages.error(request, "Invalid expiry year.")
            return redirect("bookings:payment")

        if not card_name:
            messages.error(request, "Card holder name is required.")
            return redirect("bookings:payment")

        today = timezone.localdate()
        exp_y = int(exp_year)
        exp_m = int(exp_month)
        if exp_y < today.year or (exp_y == today.year and exp_m < today.month):
            messages.error(request, "Card is expired.")
            return redirect("bookings:payment")

        email = (request.session.get("email", "") or "").strip()
        mobile = (request.session.get("mobile", "") or "").strip()
        seat_assignments = request.session.get("seat_assignments") or {}

        booking_pairs = []
        created_outbound_ids = []
        created_return_ids = []

        try:
            with transaction.atomic():
                for i, name in enumerate(passenger_list):
                    gender = gender_list[i] if i < len(gender_list) else "MALE"
                    chosen_seat = (seat_assignments.get(str(i)) or "").strip().upper()

                    outbound_booking = Booking.objects.create(
                        user=request.user,
                        flight=outbound,
                        passenger_name=name,
                        email=email,
                        mobile=mobile,
                        gender=gender,
                        charges=charges,
                        total_fare=(outbound_base + charges),
                        status="confirmed",
                        seat_no=chosen_seat,
                    )
                    created_outbound_ids.append(outbound_booking.id)

                    if chosen_seat:
                        seat_obj, _ = Seat.objects.get_or_create(
                            flight=outbound,
                            seat_code=chosen_seat
                        )

                        if seat_obj.booking_id or seat_obj.status == "booked":
                            raise ValueError(f"Seat {chosen_seat} already booked.")

                        if (
                            seat_obj.status == "reserved"
                            and seat_obj.reserved_until
                            and seat_obj.reserved_until > timezone.now()
                            and seat_obj.reserved_by_id not in [None, request.user.id]
                        ):
                            raise ValueError(f"Seat {chosen_seat} reserved by another user.")

                        seat_obj.booking = outbound_booking
                        seat_obj.status = "booked"
                        seat_obj.reserved_by = None
                        seat_obj.reserved_until = None
                        seat_obj.save(update_fields=["booking", "status", "reserved_by", "reserved_until"])

                    return_booking_id = None
                    if return_flight:
                        return_booking = Booking.objects.create(
                            user=request.user,
                            flight=return_flight,
                            passenger_name=name,
                            email=email,
                            mobile=mobile,
                            gender=gender,
                            charges=charges,
                            total_fare=(return_base + charges),
                            status="confirmed",
                        )
                        created_return_ids.append(return_booking.id)
                        return_booking_id = return_booking.id

                    booking_pairs.append({
                        "outbound": outbound_booking.id,
                        "return": return_booking_id
                    })

        except Exception as e:
            Seat.objects.filter(booking_id__in=created_outbound_ids).update(
                booking=None,
                status="available",
                reserved_by=None,
                reserved_until=None
            )
            Booking.objects.filter(id__in=created_return_ids).delete()
            messages.error(request, f"Payment failed: {str(e)}")
            return redirect("bookings:select_seat", flight_id=outbound.id)

        request.session["booking_pairs"] = booking_pairs
        request.session["booking_id"] = booking_pairs[0]["outbound"]
        request.session["return_booking_id"] = booking_pairs[0]["return"]

        # Delay notification create after successful booking
        try:
            create_delay_notification_for_flight(
                request.user,
                outbound,
                seat_class=seat_class,
                threshold=20
            )

            if return_flight:
                create_delay_notification_for_flight(
                    request.user,
                    return_flight,
                    seat_class=seat_class,
                    threshold=20
                )
        except Exception as e:
            print("Delay notification error:", e)

        request.session["seat_selection_done"] = False
        request.session["seat_assignments"] = {}

        return redirect("bookings:success")

    return render(request, "flights/payment.html", {
        "amount": round(total_amount, 2),
        "passenger_count": passenger_count,
        "seat_class": seat_class,
        "outbound_base": round(outbound_base, 2),
        "return_base": round(return_base, 2),
        "charges": round(charges, 2),
        "has_return": bool(return_flight),
        "year_range": year_range,
        "month_range": month_range,
    })
# =========================
# SUCCESS
# =========================
@login_required
def success(request):
    pairs = request.session.get("booking_pairs") or []
    if not pairs:
        return redirect("flights:home")

    first_outbound_booking = get_object_or_404(Booking, id=pairs[0]["outbound"])
    outbound_flight = first_outbound_booking.flight

    return render(request, "flights/success.html", {
        "booking_id": request.session.get("booking_id"),
        "return_booking_id": request.session.get("return_booking_id"),
        "origin_code": _safe_code(getattr(outbound_flight, "source", ""), "ORG"),
        "dest_code": _safe_code(getattr(outbound_flight, "destination", ""), "DST"),
    })


# =========================
# TICKET HTML + PDF
# =========================
def _ticket_context_from_booking(booking, seat_class):
    flight = booking.flight
    charges = float(getattr(booking, "charges", 0) or 0)
    total = float(getattr(booking, "total_fare", 0) or 0)
    base = max(total - charges, 0)

    return {
        "booking_ref": booking.id,
        "booking_date": booking.created_at.strftime("%d %b %Y - %H:%M") if getattr(booking, "created_at", None) else "",
        "date": fmt_date(getattr(flight, "date", None)),
        "seat_class": seat_class.title(),
        "email": booking.email,
        "mobile": booking.mobile,
        "passenger_name": booking.passenger_name,
        "seat_no": getattr(booking, "seat_no", ""),
        "origin_code": _safe_code(getattr(flight, "source", ""), "ORG"),
        "dest_code": _safe_code(getattr(flight, "destination", ""), "DST"),
        "depart_time": fmt_time(getattr(flight, "departure_time", None)),
        "arrive_time": fmt_time(getattr(flight, "arrival_time", None)),
        "airline": getattr(flight, "airline", "") or "-",
        "flight_no": getattr(flight, "flight_no", "") or "-",
        "base_fare": base,
        "charges": charges,
        "total_fare": total,
    }


@login_required
def ticket(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    seat_class = (request.session.get("seat_class") or "economy").strip().lower()
    context = _ticket_context_from_booking(booking, seat_class)
    context["ticket_title"] = "E-Ticket"
    return render(request, "flights/print_ticket.html", context)


@login_required
def ticket_pdf(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    seat_class = (request.session.get("seat_class") or "economy").strip().lower()
    ctx = _ticket_context_from_booking(booking, seat_class)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="ticket_{booking.id}.pdf"'

    c = canvas.Canvas(response, pagesize=A4)
    w, h = A4

    c.setFont("Helvetica-Bold", 18)
    c.drawString(20 * mm, h - 25 * mm, "FLIGHT - E-Ticket")
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, h - 32 * mm, f"Booking Ref: {ctx['booking_ref']}")
    c.drawString(20 * mm, h - 38 * mm, f"Booked On: {ctx['booking_date']}")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, h - 55 * mm, "Passenger")
    c.setFont("Helvetica", 11)
    c.drawString(20 * mm, h - 62 * mm, f"Name: {ctx['passenger_name']}")
    c.drawString(20 * mm, h - 69 * mm, f"Email: {ctx['email']}")
    c.drawString(20 * mm, h - 76 * mm, f"Mobile: {ctx['mobile']}")
    if ctx["seat_no"]:
        c.drawString(20 * mm, h - 83 * mm, f"Seat: {ctx['seat_no']}")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, h - 98 * mm, "Flight")
    c.setFont("Helvetica", 11)
    c.drawString(20 * mm, h - 105 * mm, f"{ctx['airline']}  {ctx['flight_no']}")
    c.drawString(20 * mm, h - 112 * mm, f"{ctx['origin_code']} → {ctx['dest_code']}   Date: {ctx['date']}")
    c.drawString(20 * mm, h - 119 * mm, f"Departure: {ctx['depart_time']}   Arrival: {ctx['arrive_time']}")
    c.drawString(20 * mm, h - 126 * mm, f"Class: {ctx['seat_class']}")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, h - 142 * mm, "Fare")
    c.setFont("Helvetica", 11)
    c.drawString(20 * mm, h - 149 * mm, f"Base Fare: ₹{ctx['base_fare']:.0f}")
    c.drawString(20 * mm, h - 156 * mm, f"Charges: ₹{ctx['charges']:.0f}")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, h - 164 * mm, f"Total: ₹{ctx['total_fare']:.0f}")

    qr_data = f"BOOKING:{ctx['booking_ref']}|{ctx['origin_code']}-{ctx['dest_code']}|{ctx['date']}"
    qr = QrCodeWidget(qr_data)
    bounds = qr.getBounds()
    size = 40 * mm
    width = bounds[2] - bounds[0]
    heightb = bounds[3] - bounds[1]
    d = Drawing(size, size, transform=[size / width, 0, 0, size / heightb, 0, 0])
    d.add(qr)
    renderPDF.draw(d, c, w - 70 * mm, h - 85 * mm)

    c.showPage()
    c.save()
    return response


# =========================
# CANCEL BOOKING
# =========================
@login_required
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if booking.status == "cancelled":
        messages.info(request, "This booking is already cancelled.")
        return redirect("bookings:my_bookings")

    booking.status = "cancelled"
    booking.initiate_refund()

    Seat.objects.filter(booking=booking).update(booking=None)
    booking.seat_no = ""
    booking.save()

    messages.success(request, f"Booking cancelled successfully. Refund of ₹{booking.refund_amount} initiated.")
    return redirect("bookings:my_bookings")


# =========================
# ROUND TRIP HELPERS
# =========================
@login_required
def select_outbound(request, flight_id):
    request.session["outbound_flight_id"] = flight_id
    request.session["flight_id"] = flight_id
    request.session["trip_type"] = "2"

    request.session.pop("return_flight_id", None)

    rt_origin = request.session.get("rt_origin")
    rt_destination = request.session.get("rt_destination")
    rt_return_date = request.session.get("rt_return_date")

    if not rt_origin or not rt_destination or not rt_return_date:
        return redirect("bookings:review", flight_id=flight_id)

    seat_class = request.session.get("seat_class", "economy")

    return redirect(
        f"/results/?TripType=2"
        f"&Origin={rt_destination}"
        f"&Destination={rt_origin}"
        f"&DepartDate={rt_return_date}"
        f"&ReturnDate={rt_return_date}"
        f"&SeatClass={seat_class}"
        f"&phase=return"
    )


@login_required
def select_return(request, flight_id):
    outbound_id = request.session.get("outbound_flight_id")

    if not outbound_id:
        messages.error(request, "Please select outbound flight first.")
        return redirect("flights:home")

    if str(outbound_id) == str(flight_id):
        messages.error(request, "Return flight cannot be same as outbound flight.")
        return redirect("bookings:review", flight_id=outbound_id)

    request.session["return_flight_id"] = flight_id
    request.session["trip_type"] = "2"

    return redirect("bookings:review", flight_id=outbound_id)


# =========================
# TICKET SHORTCUTS
# =========================
@login_required
def ticket_outbound(request):
    booking_id = request.session.get("booking_id")
    if not booking_id:
        return redirect("flights:home")
    return redirect("bookings:ticket", booking_id=booking_id)


@login_required
def ticket_return(request):
    return_booking_id = request.session.get("return_booking_id")
    if not return_booking_id:
        return redirect("bookings:ticket_outbound")
    return redirect("bookings:ticket", booking_id=return_booking_id)


# =========================
# OPTIONAL: REFUND PROCESS
# =========================
@login_required
def process_refund(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    booking.refund_status = "processed"
    booking.refund_processed_at = timezone.now()
    booking.save()
    messages.success(request, "Refund processed successfully.")
    return redirect("bookings:my_bookings")


# =========================
# HOTEL BOOKING
# =========================
@login_required
def book_hotel(request):
    if request.method != "POST":
        return redirect("flights:home")

    destination_slug = (request.POST.get("destination_slug") or "").strip().lower()
    destination_code = (request.POST.get("destination_code") or "").strip().upper()

    hotel_name = (request.POST.get("hotel_name") or "").strip()
    hotel_city = (request.POST.get("hotel_city") or "").strip()
    price = float(request.POST.get("price_per_night") or 0)

    checkin = parse_date(request.POST.get("checkin_date") or "")
    checkout = parse_date(request.POST.get("checkout_date") or "")
    rooms = int(request.POST.get("rooms") or 1)

    if not (destination_slug and hotel_name and checkin and checkout):
        messages.error(request, "Please fill hotel booking details.")
        return redirect("flights:destination_detail", slug=destination_slug)

    if checkout <= checkin:
        messages.error(request, "Checkout date must be after check-in date.")
        return redirect("flights:destination_detail", slug=destination_slug)

    HotelBooking.objects.create(
        user=request.user,
        destination_slug=destination_slug,
        destination_code=destination_code,
        hotel_name=hotel_name,
        hotel_city=hotel_city,
        price_per_night=price,
        checkin_date=checkin,
        checkout_date=checkout,
        rooms=max(rooms, 1),
    )

    messages.success(request, "✅ Hotel booking successful!")
    return redirect("bookings:my_hotel_bookings")


@login_required
def my_hotel_bookings(request):
    items = HotelBooking.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "bookings/my_hotel_bookings.html", {"items": items})