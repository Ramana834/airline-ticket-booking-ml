# Voice-Enabled Flight Booking (Speech -> NLP -> Booking)

This project supports **voice commands** to search flights and book them.

## 1) Setup (Windows)
```bash
# go to project folder (same folder as manage.py)
cd airline_ticket_ml

# create venv
python -m venv env

# activate
env\Scripts\activate

# install requirements
pip install -r requirements.txt

# migrate
python manage.py migrate

# load flights (generates fares for economy/business/first)
python manage.py load_flights

# run
python manage.py runserver
```

## 2) How to use Voice
Your browser must support the **Web Speech API** (Chrome/Edge recommended).

### On Home page
Click **🎙️ Voice** and say:
- `search flights from Hyderabad to Delhi on 5 Feb economy`
- `search flights from Mumbai to Bangalore tomorrow business`

It will auto-fill the form and submit.

### On Search Results page
Click **🎙️ Voice** and say:
- `book flight 2`
- `select flight 1`

It will open the selected flight review page.

### On Review page
Click **🎙️ Voice** and say:
- `confirm booking`
- `proceed to payment`

## 3) Important Rules Implemented
- If you search for **today**, flights with departure time **before current time** are hidden.
- If a flight already departed (today), it **cannot be booked** (blocked on Review/Payment).
- Economy / Business / First class prices are supported:
  - If CSV provides fares, those are used.
  - If CSV doesn't provide fares, Business and First fares are derived from Economy (1.6x and 2.2x).

