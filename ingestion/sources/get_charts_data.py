from random import random
from time import sleep
import csv
import os
import tempfile
from datetime import date as calendar_date, timedelta
from pathlib import Path

from dotenv import load_dotenv

import requests


CHART_FIELDS = [
    "rank",
    "id",
    "artist_names",
    "track_name",
    "source",
    "peak_rank",
    "days_on_chart",
    "streams",
]


def get_charts_token():
    return os.getenv("SPOTIFY_CHARTS_TOKEN") or os.getenv("BEARER_TOKEN")


def chart_entry_to_row(entry):
    """Flatten one chart entry into the CSV columns."""
    chart_data = entry["chartEntryData"]
    track = entry["trackMetadata"]
    track_uri = track["trackUri"]
    if not isinstance(track_uri, str) or not track_uri:
        raise ValueError("Spotify Charts entry has no track URI")
    return {
        "rank": chart_data["currentRank"],
        "id": track_uri.removeprefix("spotify:track:"),
        "artist_names": ", ".join(artist["name"] for artist in track["artists"]),
        "track_name": track["trackName"],
        "source": ", ".join(label["name"] for label in track["labels"]),
        "peak_rank": chart_data["peakRank"],
        "days_on_chart": chart_data["appearancesOnChart"],
        "streams": chart_data["rankingMetric"]["value"],
    }

def get_charts_data(token, date="2026-11-02", region="global", period="daily"):
    """
    Fetches the Spotify charts data for a given date and region using the provided bearer token.
    
    Args:
        token (str): The bearer token for authentication.
        date (str): The chart date, or "latest".
        region (str): The region for which to fetch the charts data.
        period (str): "daily" or "weekly".

    Returns:
        dict: The JSON response containing the charts data.
    """
    response = requests.get(
        f"https://charts-spotify-com-service.spotify.com/auth/v0/charts/regional-{region}-{period}/{date}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    response.raise_for_status()

    return response.json()


def save_charts_to_csv(chart, date, region, output_dir="data", period="daily"):
    """
    Saves the Spotify charts data with track IDs to a CSV file.

    Args:
        chart (dict): The JSON response containing the charts data.
        date (str): The date for which the charts data was fetched.
        region (str): The region for which the charts data was fetched.
        output_dir (str or Path): Output directory, created if needed.
    """
    suffix = "_weekly" if period == "weekly" else ""
    output_path = Path(output_dir) / f"charts_data_{date}_{region}{suffix}.csv"
    entries = chart["entries"]
    if not isinstance(entries, list):
        raise ValueError("Spotify Charts response must contain an entries list")
    if not entries:
        raise ValueError("Spotify Charts returned no entries")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", newline="", encoding="utf-8", dir=output_path.parent,
            prefix=output_path.name + ".", suffix=".tmp", delete=False,
        ) as csv_file:
            temporary_path = Path(csv_file.name)
            writer = csv.DictWriter(csv_file, fieldnames=CHART_FIELDS)
            writer.writeheader()
            writer.writerows(chart_entry_to_row(entry) for entry in entries)
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    print(f"Saved {len(entries)} entries to {output_path}", flush=True)
    return output_path


def save_multiple_charts_to_csv(
    token, start_date, end_date, regions, output_file="data/charts_data.csv"
):
    """Fetch an inclusive YYYY-MM-DD date range for each region into one CSV.

    Args:
        token (str): The bearer token for authentication.
        start_date (str): The start date in YYYY-MM-DD format.
        end_date (str): The end date in YYYY-MM-DD format.
        regions (list or str): Spotify region codes, e.g. ["global", "ee", "us"].
        output_file (str or Path): CSV path; parent directories are created if needed.
    """

    first_date = calendar_date.fromisoformat(start_date)
    last_date = calendar_date.fromisoformat(end_date)
    if first_date > last_date:
        raise ValueError("start_date must be on or before end_date")

    if isinstance(regions, str):
        regions = [regions]
    # Normalize and deduplicate regions so repeated codes do not duplicate rows.
    regions = list(dict.fromkeys(region.strip().lower() for region in regions))
    if not regions or any(not region for region in regions):
        raise ValueError("Provide at least one non-empty region code")

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    total_entries = 0
    try:
        # Stream rows to disk; publish the combined file only after all requests succeed.
        with tempfile.NamedTemporaryFile(
            mode="w", newline="", encoding="utf-8", dir=output_path.parent,
            prefix=output_path.name + ".", suffix=".tmp", delete=False,
        ) as csv_file:
            temporary_path = Path(csv_file.name)
            writer = csv.DictWriter(csv_file, fieldnames=["date", "region", *CHART_FIELDS])
            writer.writeheader()

            current_date = first_date
            while current_date <= last_date:
                date_string = current_date.isoformat()
                for region in regions:
                    chart = get_charts_data(token, date=date_string, region=region)
                    for entry in chart["entries"]:
                        writer.writerow({
                            "date": date_string,
                            "region": region,
                            **chart_entry_to_row(entry),
                        })
                        total_entries += 1
                    print(f"Fetched {date_string} / {region}: {len(chart['entries'])} entries")
                if current_date == last_date:
                    break
                current_date += timedelta(days=1)
                sleep(0.3 + random() * 0.2)  # Avoid rate limiting; adjust as needed.

        os.replace(temporary_path, output_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    print(f"Saved {total_entries} entries to {output_path}")
    return output_path


if __name__ == "__main__":
    load_dotenv()
    token = get_charts_token()
    if not token:
        raise ValueError("Set SPOTIFY_CHARTS_TOKEN (or BEARER_TOKEN) for Spotify Charts")

    save_multiple_charts_to_csv(
        token,
        start_date="2026-10-20", # YYYY-MM-DD format
        end_date="2026-11-02", # YYYY-MM-DD format
        regions=["global", "ee"], # Spotify region codes, e.g. ["global", "ee", "us"]
        output_file="data/charts_data.csv",
    )


"""
[{"code":"GLOBAL","readableName":"Global"},
{"code":"AR","readableName":"Argentina"},{"code":"AU","readableName":"Australia"},
{"code":"AT","readableName":"Austria"},{"code":"BY","readableName":"Belarus"},
{"code":"BE","readableName":"Belgium"},{"code":"BO","readableName":"Bolivia"},
{"code":"BR","readableName":"Brazil"},{"code":"BG","readableName":"Bulgaria"},
{"code":"CA","readableName":"Canada"},{"code":"CL","readableName":"Chile"},
{"code":"CO","readableName":"Colombia"},{"code":"CR","readableName":"Costa Rica"},
{"code":"CY","readableName":"Cyprus"},{"code":"CZ","readableName":"Czech Republic"},
{"code":"DK","readableName":"Denmark"},{"code":"DO","readableName":"Dominican Republic"},
{"code":"EC","readableName":"Ecuador"},{"code":"EG","readableName":"Egypt"},
{"code":"SV","readableName":"El Salvador"},{"code":"EE","readableName":"Estonia"},
{"code":"FI","readableName":"Finland"},{"code":"FR","readableName":"France"},
{"code":"DE","readableName":"Germany"},{"code":"GR","readableName":"Greece"},
{"code":"GT","readableName":"Guatemala"},{"code":"HN","readableName":"Honduras"},
{"code":"HK","readableName":"Hong Kong"},{"code":"HU","readableName":"Hungary"},
{"code":"IS","readableName":"Iceland"},{"code":"IN","readableName":"India"},
{"code":"ID","readableName":"Indonesia"},{"code":"IE","readableName":"Ireland"},
{"code":"IL","readableName":"Israel"},{"code":"IT","readableName":"Italy"},
{"code":"JP","readableName":"Japan"},{"code":"KZ","readableName":"Kazakhstan"},
{"code":"LV","readableName":"Latvia"},{"code":"LT","readableName":"Lithuania"},
{"code":"LU","readableName":"Luxembourg"},{"code":"MY","readableName":"Malaysia"},
{"code":"MX","readableName":"Mexico"},{"code":"MA","readableName":"Morocco"},
{"code":"NL","readableName":"Netherlands"},{"code":"NZ","readableName":"New Zealand"},
{"code":"NI","readableName":"Nicaragua"},{"code":"NG","readableName":"Nigeria"},
{"code":"NO","readableName":"Norway"},{"code":"PK","readableName":"Pakistan"},
{"code":"PA","readableName":"Panama"},{"code":"PY","readableName":"Paraguay"},
{"code":"PE","readableName":"Peru"},{"code":"PH","readableName":"Philippines"},
{"code":"PL","readableName":"Poland"},{"code":"PT","readableName":"Portugal"},
{"code":"RO","readableName":"Romania"},{"code":"SA","readableName":"Saudi Arabia"},
{"code":"SG","readableName":"Singapore"},{"code":"SK","readableName":"Slovakia"},
{"code":"ZA","readableName":"South Africa"},{"code":"KR","readableName":"South Korea"},
{"code":"ES","readableName":"Spain"},{"code":"SE","readableName":"Sweden"},
{"code":"CH","readableName":"Switzerland"},{"code":"TW","readableName":"Taiwan"},
{"code":"TH","readableName":"Thailand"},{"code":"TR","readableName":"Turkey"},
{"code":"AE","readableName":"UAE"},{"code":"UA","readableName":"Ukraine"},
{"code":"GB","readableName":"United Kingdom"},{"code":"UY","readableName":"Uruguay"},
{"code":"US","readableName":"USA"},{"code":"VE","readableName":"Venezuela"},
{"code":"VN","readableName":"Vietnam"}]"""
