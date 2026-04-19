from bs4 import BeautifulSoup as bs
from urllib.request import urlopen
import pandas as pd

print("Fetching Data of Different Airports...")

rows = []

# --- Top airports in world ---
try:
    page = urlopen("https://gettocenter.com/airports/top-100-airports-in-world")
    soup = bs(page, "html.parser")

    tr_list = soup.find_all("tr")
    for tr in tr_list:
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue

        airport = tds[1].get_text(strip=True)
        code = tds[2].get_text(strip=True).upper()
        city = tds[3].get_text(strip=True)
        country = tds[4].get_text(strip=True)

        if code and len(code) == 3:
            rows.append([city, airport, code, country])

    print(f"World airports fetched: {len(rows)}")
except Exception as e:
    print("World airports fetch failed:", e)


# --- Top airports in India ---
try:
    page = urlopen("https://www.worlddata.info/asia/india/airports.php")
    soup = bs(page, "html.parser")

    table = soup.find("table")
    tr_list = table.find_all("tr")

    for tr in tr_list[1:]:
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue

        code = tds[0].get_text(strip=True).upper()
        airport = tds[1].get_text(strip=True)
        city = tds[2].get_text(strip=True)
        country = "India"

        if code and len(code) == 3:
            rows.append([city, airport, code, country])

    print("India airports added.")
except Exception as e:
    print("India airports fetch failed:", e)


# --- Create DF & remove duplicates by code ---
df = pd.DataFrame(rows, columns=["city", "airport", "code", "country"])
df = df.drop_duplicates(subset=["code"]).sort_values("code").reset_index(drop=True)

# Save to Data folder
output_path = r"Data\airports.csv"
df.to_csv(output_path, index=False)

print(f"Saved: {output_path}")
print(f"Total unique airports: {len(df)}")
print("DONE ✅")
