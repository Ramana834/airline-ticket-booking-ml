# flights/views.py
import csv
import json
import os
import re
from datetime import date, timedelta

from django.conf import settings
from django.contrib import messages
from django.db.models import Min
from django.http import JsonResponse, Http404
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import Flight


# -----------------------------
# DESTINATION META (slugs stable)
# -----------------------------
DEST_META = {
    "italy":      {"title": "London",        "banner": "images/destinations/italy.jpg",      "rating": 4.8, "code": "LHR"},
    "brazil":     {"title": "Paris",         "banner": "images/destinations/brazil.jpg",     "rating": 4.6, "code": "CDG"},
    "america":    {"title": "New York",      "banner": "images/destinations/america.jpg",    "rating": 4.7, "code": "JFK"},
    "nepal":      {"title": "Frankfurt",     "banner": "images/destinations/nepal.jpg",      "rating": 4.5, "code": "FRA"},
    "maldives":   {"title": "Amsterdam",     "banner": "images/destinations/maldives.jpg",   "rating": 4.9, "code": "AMS"},
    "indonesia":  {"title": "Los Angeles",   "banner": "images/destinations/indonesia.jpg",  "rating": 4.6, "code": "LAX"},
}

DEST_WIKI = {
    "italy": "https://en.wikipedia.org/wiki/London",
    "brazil": "https://en.wikipedia.org/wiki/Paris",
    "america": "https://en.wikipedia.org/wiki/New_York_City",
    "nepal": "https://en.wikipedia.org/wiki/Frankfurt",
    "maldives": "https://en.wikipedia.org/wiki/Amsterdam",
    "indonesia": "https://en.wikipedia.org/wiki/Los_Angeles",
}


# -----------------------------
# Airports loader (Data/airports.csv)
# columns: city, airport, code, country
# -----------------------------
_AIRPORTS = None
_CITY_TO_CODE = None
_CODE_TO_AIRPORT = None


def load_airports():
    global _AIRPORTS, _CITY_TO_CODE, _CODE_TO_AIRPORT
    if _AIRPORTS is not None:
        return _AIRPORTS, _CITY_TO_CODE, _CODE_TO_AIRPORT

    _AIRPORTS = []
    _CITY_TO_CODE = {}
    _CODE_TO_AIRPORT = {}

    path = os.path.join(settings.BASE_DIR, "Data", "airports.csv")
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                city = (row.get("city") or "").strip()
                airport = (row.get("airport") or "").strip()
                code = (row.get("code") or "").strip().upper()
                country = (row.get("country") or "").strip()
                if not code:
                    continue
                item = {"city": city, "airport": airport, "code": code, "country": country}
                _AIRPORTS.append(item)
                if city and city.lower() not in _CITY_TO_CODE:
                    _CITY_TO_CODE[city.lower()] = code
                _CODE_TO_AIRPORT[code] = item
    except Exception as e:
        print("airports.csv read error:", e)

    return _AIRPORTS, _CITY_TO_CODE, _CODE_TO_AIRPORT


def airport_options():
    src_codes = (
        Flight.objects.exclude(source_code__isnull=True)
        .exclude(source_code__exact="")
        .values_list("source_code", flat=True)
        .distinct()
    )
    dst_codes = (
        Flight.objects.exclude(destination_code__isnull=True)
        .exclude(destination_code__exact="")
        .values_list("destination_code", flat=True)
        .distinct()
    )

    all_codes = sorted(set(list(src_codes) + list(dst_codes)))
    _, _, code2a = load_airports()

    opts = []
    for code in all_codes:
        a = code2a.get(code)
        if a:
            label = f"{a['city']} - {a['airport']} ({a['code']})"
        else:
            label = code
        opts.append({"code": code, "label": label})

    return opts


def resolve_to_code(value: str) -> str:
    """Accept IATA code or city name and return a code if possible."""
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) == 3 and v.isalpha():
        return v.upper()
    _, city2code, _ = load_airports()
    return city2code.get(v.lower(), "")


def load_local_hotels(slug: str):
    path = os.path.join(settings.BASE_DIR, "Data", "hotels.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get((slug or "").lower().strip(), [])
    except Exception:
        return []


def load_emergency_numbers(slug: str):
    slug = (slug or "").lower().strip()
    slug_to_country = {
        "italy": "italy",
        "brazil": "brazil",
        "america": "usa",
        "nepal": "nepal",
        "indonesia": "indonesia",
        "maldives": "maldives",
    }
    country = slug_to_country.get(slug, "india")
    path = os.path.join(settings.BASE_DIR, "Data", "emergency_numbers.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return country, data.get(country, {"general": "112"})
    except Exception:
        return country, {"general": "112"}


# -----------------------------
# Views
# -----------------------------
def home(request):
    selected_dest = request.GET.get("dest", "").strip().upper()

    _, _, code2a = load_airports()

    popular = (
        Flight.objects.exclude(destination_code__isnull=True)
        .exclude(destination_code__exact="")
        .values("destination_code")
        .annotate(cheapest_price=Min("price"))
        .order_by("cheapest_price")[:6]
    )

    BANNER_MAP = {
        "LHR": "images/destinations/italy.jpg",
        "CDG": "images/destinations/brazil.jpg",
        "JFK": "images/destinations/america.jpg",
        "FRA": "images/destinations/nepal.jpg",
        "AMS": "images/destinations/maldives.jpg",
        "LAX": "images/destinations/indonesia.jpg",
    }

    dest_cards = []
    for row in popular:
        code = (row.get("destination_code") or "").strip().upper()
        if not code:
            continue

        a = code2a.get(code)
        title = a["city"] if a else code

        dest_cards.append({
            "slug": code.lower(),
            "title": title,
            "banner": BANNER_MAP.get(code, "images/destinations/italy.jpg"),
            "rating": 4.7,
            "cheapest_price": row.get("cheapest_price"),
            "code": code,
        })

    return render(request, "flights/home.html", {
        "airport_options": airport_options(),
        "destinations": dest_cards,
        "selected_dest": selected_dest,
    })


@login_required
def flight_list(request):
    flights = Flight.objects.all().order_by("-date")[:200]
    return render(request, "ml_features/flight_list.html", {"flights": flights})


@login_required
def search_results(request):
    trip_type = (request.GET.get("TripType") or request.session.get("trip_type") or "1").strip()
    phase = (request.GET.get("phase") or "").strip().lower()

    origin_raw = (request.GET.get("Origin") or "").strip()
    dest_raw = (request.GET.get("Destination") or "").strip()
    depart_date_raw = (request.GET.get("DepartDate") or "").strip()
    return_date_raw = (request.GET.get("ReturnDate") or "").strip()
    seat_class = (request.GET.get("SeatClass") or request.session.get("seat_class") or "economy").strip().lower()

    if not origin_raw or not dest_raw or not depart_date_raw:
        messages.error(request, "Please fill Origin, Destination and Departure Date.")
        return redirect("flights:home")

    if origin_raw.upper() == dest_raw.upper():
        messages.error(request, "Origin and Destination should be different.")
        return redirect("flights:home")

    depart_date = parse_date(depart_date_raw)
    if not depart_date:
        messages.error(request, "Invalid departure date.")
        return redirect("flights:home")

    return_date = parse_date(return_date_raw) if return_date_raw else None

    today = timezone.localdate()
    if depart_date < today:
        depart_date = today

    if return_date and return_date < today:
        return_date = today

    if trip_type == "2" and return_date and return_date < depart_date and phase != "return":
        messages.error(request, "Return date cannot be before departure date.")
        return redirect("flights:home")

    request.session["trip_type"] = trip_type
    request.session["seat_class"] = seat_class

    origin_code = resolve_to_code(origin_raw) or origin_raw.upper()
    dest_code = resolve_to_code(dest_raw) or dest_raw.upper()

    # Save round-trip search values only on first/outbound search
    if trip_type == "2" and phase != "return":
        request.session["rt_origin"] = origin_code
        request.session["rt_destination"] = dest_code
        request.session["rt_depart_date"] = depart_date.strftime("%Y-%m-%d")
        request.session["rt_return_date"] = (
            return_date.strftime("%Y-%m-%d") if return_date else depart_date.strftime("%Y-%m-%d")
        )
        request.session.pop("return_flight_id", None)

    used_date = depart_date
    flights = []
    is_connecting = False
    connecting_pairs = []

    # ----------------------------------------------------
    # A) DIRECT: exact route + exact date
    # ----------------------------------------------------
    qs_direct = Flight.objects.filter(
        source_code__iexact=origin_code,
        destination_code__iexact=dest_code,
        date=depart_date
    ).order_by("departure_time")

    flights = list(qs_direct)

    # ----------------------------------------------------
    # B) DIRECT: same route + next available date
    # ----------------------------------------------------
    if not flights:
        next_date = (
            Flight.objects.filter(
                source_code__iexact=origin_code,
                destination_code__iexact=dest_code,
                date__gte=depart_date
            )
            .order_by("date")
            .values_list("date", flat=True)
            .first()
        )
        if next_date:
            used_date = next_date
            flights = list(
                Flight.objects.filter(
                    source_code__iexact=origin_code,
                    destination_code__iexact=dest_code,
                    date=next_date
                ).order_by("departure_time")
            )
            if flights:
                messages.info(
                    request,
                    f"No direct flights on {depart_date_raw}. Showing direct flights for {used_date.strftime('%Y-%m-%d')}."
                )

    # ----------------------------------------------------
    # C) CONNECTING (1-stop)
    # ----------------------------------------------------
    if not flights:
        best_date = (
            Flight.objects.filter(source_code__iexact=origin_code, date__gte=depart_date)
            .order_by("date")
            .values_list("date", flat=True)
            .first()
        )

        if best_date:
            used_date = best_date

            leg1_qs = Flight.objects.filter(
                source_code__iexact=origin_code,
                date=used_date
            ).exclude(destination_code__iexact=origin_code).order_by("departure_time")[:300]

            leg2_qs = Flight.objects.filter(
                destination_code__iexact=dest_code,
                date=used_date
            ).exclude(source_code__iexact=dest_code).order_by("departure_time")[:300]

            leg2_by_source = {}
            for f2 in leg2_qs:
                k = (getattr(f2, "source_code", "") or "").upper()
                if not k:
                    continue
                leg2_by_source.setdefault(k, []).append(f2)

            def _time_to_minutes(t):
                if t is None:
                    return None
                if hasattr(t, "hour"):
                    return t.hour * 60 + t.minute
                s = str(t).strip()
                try:
                    hh = int(s[:2])
                    mm = int(s[3:5])
                    return hh * 60 + mm
                except Exception:
                    return None

            results = []
            for f1 in leg1_qs:
                mid = (getattr(f1, "destination_code", "") or "").upper()
                if not mid or mid == dest_code:
                    continue

                candidates = leg2_by_source.get(mid, [])
                if not candidates:
                    continue

                arr1 = _time_to_minutes(getattr(f1, "arrival_time", None))
                if arr1 is None:
                    continue

                for f2 in candidates:
                    dep2 = _time_to_minutes(getattr(f2, "departure_time", None))
                    if dep2 is None:
                        continue

                    layover = dep2 - arr1
                    if 45 <= layover <= 360:
                        results.append((f1, f2, layover))

            def _pair_price(pair):
                f1, f2, _ = pair
                p1 = float(getattr(f1, "price", 0) or 0)
                p2 = float(getattr(f2, "price", 0) or 0)
                return p1 + p2

            results.sort(key=lambda x: (_pair_price(x), getattr(x[0], "departure_time", "")))

            top = results[:30]
            if top:
                is_connecting = True
                connecting_pairs = [{"leg1": a, "leg2": b} for (a, b, _) in top]
                messages.info(
                    request,
                    f"No direct flights found. Showing 1-stop connecting flights for {used_date.strftime('%Y-%m-%d')}."
                )

    # ----------------------------------------------------
    # Display price compute
    # ----------------------------------------------------
    prices = []
    if not is_connecting:
        for f in flights:
            f.display_price = int(f.fare_for(seat_class) or 0)
            prices.append(f.display_price)
    else:
        for p in connecting_pairs:
            p["leg1"].display_price = int(p["leg1"].fare_for(seat_class) or 0)
            p["leg2"].display_price = int(p["leg2"].fare_for(seat_class) or 0)
            total = p["leg1"].display_price + p["leg2"].display_price
            p["total_price"] = total
            prices.append(total)

    return render(request, "flights/search_results.html", {
        "flights": flights,
        "connecting_pairs": connecting_pairs,
        "is_connecting": is_connecting,
        "origin": origin_code,
        "destination": dest_code,
        "depart_date": used_date.strftime("%Y-%m-%d"),
        "seat_class": seat_class,
        "trip_type": trip_type,
        "phase": phase,
        "return_date": return_date.strftime("%Y-%m-%d") if return_date else "",
        "min_price": min(prices) if prices else 0,
        "max_price": max(prices) if prices else 0,
    })


def destination_detail(request, slug):
    slug = (slug or "").lower().strip()

    meta = DEST_META.get(slug)

    if not meta and len(slug) == 3 and slug.isalpha():
        code = slug.upper()
        _, _, code2a = load_airports()
        a = code2a.get(code)
        title = a["city"] if a else code

        meta = {
            "title": title,
            "banner": "images/destinations/italy.jpg",
            "rating": 4.7,
            "code": code,
        }

    if not meta:
        raise Http404("Destination not found")

    code = (meta.get("code") or "").upper()

    cheapest = (
        Flight.objects.filter(destination_code__iexact=code)
        .order_by("price")
        .values_list("price", flat=True)
        .first()
    )

    today = timezone.localdate()
    best = (
        Flight.objects.filter(destination_code__iexact=code, date__gte=today)
        .order_by("date", "price", "departure_time")
        .values("source_code", "date")
        .first()
    )

    if best:
        origin = (best.get("source_code") or "BOM").upper()
        depart_date = best.get("date").strftime("%Y-%m-%d")
        book_url = f"/results/?Origin={origin}&Destination={code}&DepartDate={depart_date}&SeatClass=economy"
    else:
        book_url = "/"

    hotels_slug = slug if slug in DEST_META else "italy"
    hotels = load_local_hotels(hotels_slug)
    emergency_country, emergency = load_emergency_numbers(hotels_slug)

    return render(request, "flights/destination_detail.html", {
        "slug": slug,
        "title": meta["title"],
        "banner": meta["banner"],
        "rating": meta["rating"],
        "cheapest_price": cheapest,
        "book_url": book_url,
        "wiki_url": DEST_WIKI.get(hotels_slug),
        "hotels": hotels,
        "emergency_country": emergency_country,
        "emergency": emergency,
        "dest_code": code,
    })


def route_reference(request):
    origin = (request.GET.get("origin") or "").strip()
    destination = (request.GET.get("destination") or "").strip()

    _, city2code, code2a = load_airports()

    def lookup(v: str):
        if not v:
            return None
        vv = v.strip()
        if len(vv) == 3 and vv.isalpha():
            return code2a.get(vv.upper())
        code = city2code.get(vv.lower())
        if code:
            return code2a.get(code)
        return None

    a1 = lookup(origin)
    a2 = lookup(destination)

    route = None
    if a1 and a2:
        route = {
            "from": {"city": a1["city"], "code": a1["code"], "name": a1["airport"], "country": a1["country"]},
            "to": {"city": a2["city"], "code": a2["code"], "name": a2["airport"], "country": a2["country"]},
        }

    return render(request, "flights/route_reference.html", {
        "origin": origin,
        "destination": destination,
        "route": route,
        "route_from_query": f"{a1['airport']}, {a1['city']}, {a1['country']}" if a1 else "",
        "route_to_query": f"{a2['airport']}, {a2['city']}, {a2['country']}" if a2 else "",
    })


VOICE_CITY_ALIASES = {
    "bangalore": {"city": "Bengaluru", "lookup": "bangalore"},
    "bengaluru": {"city": "Bengaluru", "lookup": "bangalore"},
    "vizag": {"city": "Visakhapatnam", "lookup": "visakhapatnam"},
    "vishakapatnam": {"city": "Visakhapatnam", "lookup": "visakhapatnam"},
    "visakhapatnam": {"city": "Visakhapatnam", "lookup": "visakhapatnam"},
    "bombay": {"city": "Mumbai", "lookup": "mumbai"},
    "mumbai": {"city": "Mumbai", "lookup": "mumbai"},
    "madras": {"city": "Chennai", "lookup": "chennai"},
    "chennai": {"city": "Chennai", "lookup": "chennai"},
    "calcutta": {"city": "Kolkata", "lookup": "kolkata"},
    "kolkata": {"city": "Kolkata", "lookup": "kolkata"},
    "cochin": {"city": "Kochi", "lookup": "kochi"},
    "kochi": {"city": "Kochi", "lookup": "kochi"},
    "trivandrum": {"city": "Thiruvananthapuram", "lookup": "trivandrum"},
    "thiruvananthapuram": {"city": "Thiruvananthapuram", "lookup": "trivandrum"},
    "goa": {"city": "Goa", "lookup": "goa", "code": "GOI"},
}

VOICE_NUMBER_WORDS = {
    "one": 1,
    "first": 1,
    "two": 2,
    "second": 2,
    "three": 3,
    "third": 3,
    "four": 4,
    "fourth": 4,
    "five": 5,
    "fifth": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

VOICE_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _voice_city_catalog():
    airports, _, _ = load_airports()
    catalog = {}

    for row in airports:
        city = (row.get("city") or "").strip()
        code = (row.get("code") or "").strip().upper()
        if city and code:
            catalog[city.lower()] = {"city": city, "lookup": city.lower(), "code": code}

    for alias, meta in VOICE_CITY_ALIASES.items():
        code = meta.get("code") or resolve_to_code(meta["lookup"])
        if code:
            catalog[alias] = {"city": meta["city"], "lookup": meta["lookup"], "code": code}

    return catalog


def _extract_city_mentions(transcript: str):
    mentions = []

    for phrase, meta in sorted(_voice_city_catalog().items(), key=lambda item: len(item[0]), reverse=True):
        pattern = re.compile(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])")
        for match in pattern.finditer(transcript):
            mentions.append({
                "start": match.start(),
                "end": match.end(),
                "city": meta["city"],
                "code": meta["code"],
            })

    mentions.sort(key=lambda item: (item["start"], -(item["end"] - item["start"])))
    filtered = []
    for item in mentions:
        if filtered and item["start"] < filtered[-1]["end"]:
            continue
        filtered.append(item)
    return filtered


def _city_after_keyword(transcript: str, mentions, keyword: str):
    keyword_match = re.search(rf"\b{keyword}\b", transcript)
    if not keyword_match:
        return None

    for item in mentions:
        if item["start"] >= keyword_match.end():
            return item
    return None


def _city_after_position(mentions, start_pos: int, end_pos=None):
    for item in mentions:
        if item["start"] < start_pos:
            continue
        if end_pos is not None and item["start"] >= end_pos:
            continue
        return item
    return None


def _parse_voice_date(transcript: str):
    today = timezone.localdate()
    cleaned = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", transcript)

    if "day after tomorrow" in cleaned:
        return today + timedelta(days=2)
    if "tomorrow" in cleaned:
        return today + timedelta(days=1)
    if "today" in cleaned:
        return today
    if "next week" in cleaned:
        return today + timedelta(days=7)

    iso_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", cleaned)
    if iso_match:
        try:
            return date.fromisoformat(iso_match.group(0))
        except ValueError:
            pass

    slash_match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", cleaned)
    if slash_match:
        day = int(slash_match.group(1))
        month = int(slash_match.group(2))
        year = int(slash_match.group(3)) if slash_match.group(3) else today.year
        if year < 100:
            year += 2000
        try:
            parsed = date(year, month, day)
            if not slash_match.group(3) and parsed < today:
                parsed = date(year + 1, month, day)
            return parsed
        except ValueError:
            pass

    month_pattern = "|".join(sorted(VOICE_MONTHS.keys(), key=len, reverse=True))
    match_a = re.search(rf"\b({month_pattern})\s+(\d{{1,2}})(?:\s+(\d{{4}}))?\b", cleaned)
    if match_a:
        month = VOICE_MONTHS[match_a.group(1)]
        day = int(match_a.group(2))
        year = int(match_a.group(3)) if match_a.group(3) else today.year
        try:
            parsed = date(year, month, day)
            if not match_a.group(3) and parsed < today:
                parsed = date(year + 1, month, day)
            return parsed
        except ValueError:
            pass

    match_b = re.search(rf"\b(\d{{1,2}})\s+({month_pattern})(?:\s+(\d{{4}}))?\b", cleaned)
    if match_b:
        day = int(match_b.group(1))
        month = VOICE_MONTHS[match_b.group(2)]
        year = int(match_b.group(3)) if match_b.group(3) else today.year
        try:
            parsed = date(year, month, day)
            if not match_b.group(3) and parsed < today:
                parsed = date(year + 1, month, day)
            return parsed
        except ValueError:
            pass

    return None


def _parse_passenger_count(transcript: str):
    digit_match = re.search(r"\b(\d+)\s+(passengers?|people|persons?|tickets?|travellers?|travelers?)\b", transcript)
    if digit_match:
        return int(digit_match.group(1))

    for word, number in VOICE_NUMBER_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\s+(passengers?|people|persons?|tickets?|travellers?|travelers?)\b", transcript):
            return number

    return 1


def _parse_travel_class(transcript: str):
    if "business class" in transcript or re.search(r"\bbusiness\b", transcript):
        return "business"
    if "first class" in transcript or re.search(r"\bfirst\b", transcript):
        return "first"
    return "economy"


def _extract_search_slots(transcript: str):
    mentions = _extract_city_mentions(transcript)
    from_matches = list(re.finditer(r"\bfrom\b", transcript))
    to_matches = list(re.finditer(r"\bto\b", transcript))

    source = None
    destination = None

    if from_matches:
        from_match = from_matches[-1]
        source = _city_after_position(mentions, from_match.end())

        to_after_from = next((m for m in to_matches if m.start() > from_match.start()), None)
        if to_after_from:
            destination = _city_after_position(mentions, to_after_from.end())

    if to_matches and not destination:
        if from_matches and to_matches[0].start() < from_matches[-1].start():
            destination = _city_after_position(mentions, to_matches[0].end(), from_matches[-1].start())
        else:
            destination = _city_after_position(mentions, to_matches[-1].end())

    if from_matches and not source:
        source = _city_after_position(mentions, from_matches[-1].end())

    if not source and not destination and len(mentions) >= 2:
        source = mentions[0]
        destination = mentions[1]
    elif source and not destination:
        for item in mentions:
            if item["start"] > source["start"]:
                destination = item
                break
    elif destination and not source:
        previous = [item for item in mentions if item["start"] < destination["start"]]
        if previous:
            source = previous[-1]

    parsed_date = _parse_voice_date(transcript)

    return {
        "source": source["city"] if source else None,
        "source_code": source["code"] if source else None,
        "destination": destination["city"] if destination else None,
        "destination_code": destination["code"] if destination else None,
        "date": parsed_date.isoformat() if parsed_date else None,
        "passengers": _parse_passenger_count(transcript),
        "travel_class": _parse_travel_class(transcript),
    }


def voice_parse(request):
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        payload = {}

    # Accept both transcript and text.
    transcript = (payload.get("transcript") or payload.get("text") or "").strip().lower()

    if not transcript:
        return JsonResponse({"ok": False})

    if any(k in transcript for k in ["confirm booking", "confirm", "book now", "proceed"]):
        return JsonResponse({"ok": True, "intent": "confirm"})

    slots = _extract_search_slots(transcript)
    has_search_signal = any(word in transcript for word in [
        "flight", "book", "search", "go", "travel", "need", "want", "from", "to"
    ])
    has_search_data = any([slots["source"], slots["destination"], slots["date"]])

    if has_search_signal and has_search_data:
        return JsonResponse({
            "ok": True,
            "intent": "search",
            "source": slots["source"],
            "destination": slots["destination"],
            "source_code": slots["source_code"],
            "destination_code": slots["destination_code"],
            "date": slots["date"],
            "passengers": slots["passengers"],
            "travel_class": slots["travel_class"],
            "origin": slots["source_code"],
            "destination_value": slots["destination_code"],
            "depart_date": slots["date"],
            "seat_class": slots["travel_class"],
        })

    match = re.search(r'\d+', transcript)
    wants_selection = any(word in transcript for word in ["select", "choose"]) or (
        "book" in transcript and any(word in transcript for word in ["flight", "option", "result", "card"])
    )

    if wants_selection:
        if match:
            index = int(match.group())
        else:
            index = None
            for word, num in VOICE_NUMBER_WORDS.items():
                if re.search(rf"\b{re.escape(word)}\b", transcript):
                    index = num
                    break

        if index:
            return JsonResponse({
                "ok": True,
                "intent": "select_flight",
                "flight_index": index
            })

    return JsonResponse({"ok": False})
