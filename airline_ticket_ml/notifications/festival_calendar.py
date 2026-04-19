from datetime import date

# (start_date, end_date, label, extra_percent)
FESTIVAL_WINDOWS = [

    # =======================
    # 2026
    # =======================
    (date(2026, 1, 11), date(2026, 1, 17), "Sankranti / Pongal", 30),
    (date(2026, 1, 24), date(2026, 1, 27), "Republic Day", 12),
    (date(2026, 3, 2),  date(2026, 3, 6),  "Holi", 25),
    (date(2026, 3, 18), date(2026, 3, 22), "Eid al-Fitr", 18),
    (date(2026, 5, 1),  date(2026, 6, 30), "Summer Vacation", 15),
    (date(2026, 8, 13), date(2026, 8, 16), "Independence Day", 12),
    (date(2026, 10, 15),date(2026, 10, 22),"Navratri / Dussehra", 28),
    (date(2026, 11, 6), date(2026, 11, 12),"Diwali", 40),
    (date(2026, 12, 20),date(2027, 1, 2),  "Christmas / New Year", 22),

    # =======================
    # 2027
    # =======================
    (date(2027, 1, 11), date(2027, 1, 17), "Sankranti / Pongal", 30),
    (date(2027, 3, 20), date(2027, 3, 26), "Holi", 25),
    (date(2027, 4, 10), date(2027, 4, 14), "Eid al-Fitr", 18),
    (date(2027, 5, 1),  date(2027, 6, 30), "Summer Vacation", 15),
    (date(2027, 8, 13), date(2027, 8, 16), "Independence Day", 12),
    (date(2027, 10, 8), date(2027, 10, 15),"Navratri / Dussehra", 28),
    (date(2027, 10, 29),date(2027, 11, 4), "Diwali", 40),
    (date(2027, 12, 20),date(2028, 1, 2),  "Christmas / New Year", 22),

    # =======================
    # 2028
    # =======================
    (date(2028, 1, 12), date(2028, 1, 18), "Sankranti / Pongal", 30),
    (date(2028, 3, 9),  date(2028, 3, 14), "Holi", 25),
    (date(2028, 3, 29), date(2028, 4, 2),  "Eid al-Fitr", 18),
    (date(2028, 5, 1),  date(2028, 6, 30), "Summer Vacation", 15),
    (date(2028, 8, 13), date(2028, 8, 16), "Independence Day", 12),
    (date(2028, 9, 26), date(2028, 10, 3), "Navratri / Dussehra", 28),
    (date(2028, 10, 17),date(2028, 10, 23),"Diwali", 40),
    (date(2028, 12, 20),date(2029, 1, 2),  "Christmas / New Year", 22),

    # =======================
    # 2029
    # =======================
    (date(2029, 1, 12), date(2029, 1, 18), "Sankranti / Pongal", 30),
    (date(2029, 3, 1),  date(2029, 3, 6),  "Holi", 25),
    (date(2029, 3, 20), date(2029, 3, 24), "Eid al-Fitr", 18),
    (date(2029, 5, 1),  date(2029, 6, 30), "Summer Vacation", 15),
    (date(2029, 8, 13), date(2029, 8, 16), "Independence Day", 12),
    (date(2029, 10, 11),date(2029, 10, 18),"Navratri / Dussehra", 28),
    (date(2029, 11, 5), date(2029, 11, 11),"Diwali", 40),
    (date(2029, 12, 20),date(2030, 1, 2),  "Christmas / New Year", 22),
]


def festival_boost(depart_date):
    """
    Returns (boost_percent, [reasons])
    """
    if not depart_date:
        return 0, []

    for start, end, label, boost in FESTIVAL_WINDOWS:
        if start <= depart_date <= end:
            return boost, [label]

    return 0, []
# for old predictor compatibility
FESTIVALS = [(s, e, label) for (s, e, label, boost) in FESTIVAL_WINDOWS]
