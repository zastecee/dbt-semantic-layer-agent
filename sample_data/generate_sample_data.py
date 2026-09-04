"""One-off utility script used to (re)generate sample_data/roaming_data.csv.

Run with: python3 sample_data/generate_sample_data.py
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta

COUNTRIES: dict[str, list[str]] = {
    "Mozambique": ["Vodacom Mozambique", "Movitel", "Tmcel"],
    "South Africa": ["Vodacom SA", "MTN South Africa", "Cell C"],
    "Tanzania": ["Vodacom Tanzania", "Tigo Tanzania", "Airtel Tanzania"],
    "Kenya": ["Safaricom", "Airtel Kenya", "Telkom Kenya"],
    "Zimbabwe": ["Econet Wireless", "NetOne", "Telecel Zimbabwe"],
}

RECORD_COUNT = 420
END_DATE = date(2026, 9, 1)
START_DATE = END_DATE - timedelta(days=210)


def generate_rows(rng: random.Random) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    days_span = (END_DATE - START_DATE).days
    for _ in range(RECORD_COUNT):
        event_date = START_DATE + timedelta(days=rng.randint(0, days_span))
        country = rng.choice(list(COUNTRIES.keys()))
        partner_network = rng.choice(COUNTRIES[country])
        duration = round(rng.uniform(1.0, 180.0), 2)
        total_mb = round(rng.uniform(5.0, 2048.0), 2)
        revenue = round(
            (duration * rng.uniform(0.08, 0.35)) + (total_mb * rng.uniform(0.01, 0.05)),
            2,
        )
        rows.append(
            {
                "event_date": event_date.isoformat(),
                "country": country,
                "partner_network": partner_network,
                "revenue": revenue,
                "duration": duration,
                "total_mb": total_mb,
            }
        )
    rows.sort(key=lambda row: row["event_date"])
    return rows


def main() -> None:
    rng = random.Random(42)
    rows = generate_rows(rng)
    output_path = "sample_data/roaming_data.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "event_date",
                "country",
                "partner_network",
                "revenue",
                "duration",
                "total_mb",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
