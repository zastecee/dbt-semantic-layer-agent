# Campo: EVENT_DESCRIPTION

TRAFFIC_KPIType = Literal[
    "Voice Traffic - Billed",
    "Voice Traffic - Free",
    "Voice Traffic - OOB",
    "Data Traffic - Billed",
    "Data Traffic - Free",
    "Data Traffic - OOB",
    "Sms Traffic - Billed",
    "Sms Traffic - Free",
    "Sms Traffic - OOB",
    "M-Pesa Paybill",
    "M-Pesa P2P",
    "M-Pesa Withdrawal",
    "M-Pesa Others",
    "Interconnect Local - Movitel",
    "Interconnect Local - mCel",
    "Interconnect Local - TDM",
    "Interconnect International",
    "Inflows",
    "Outflows",
]

CUSTOMER_KPIType = Literal[
    "Active GSM",
    "Voice Users",
    "Data Users",
    "Sms Users",
    "Active Mpesa base",
    "Total Revenue Users",
    "Voice Revenue Users",
    "Data Revenue Users",
    "Sms Revenue Users",
    "Total Buyers",
    "Voice Buyers",
    "Data Buyers",
    "Sms Buyers",
    "30 Days Active SUBID",
    "30 Days Active GSM SUBID",
    "30 Days Voice Users SUBID",
    "30 Days Data Users SUBID",
    "30 Days Sms Users SUBID",
    "30 Days Total Revenue Users",
    "30 Days Voice Revenue Users",
    "30 Days Data Revenue Users",
    "30 Days Sms Revenue Users",
    "30 Days Total Buyers",
    "30 Days Voice Buyers",
    "30 Days Data Buyers",
    "30 Days Sms Buyers",
    "Gross Adds Mpesa",
    "Gross Adds - GSM",
]


# ---------------------------------------------


import csv
import os
from datetime import UTC, datetime
from typing import Literal

from dateutil.relativedelta import relativedelta

# Load the traffic dataset from a CSV file
_dir = os.path.dirname(os.path.abspath(__file__))
_datasets_dir = os.path.join(_dir, "..", "..", "..", "datasets")
with open(
    os.path.join(_datasets_dir, "traffic_dataset.csv"),
    mode="r",
    encoding="iso-8859-1",
    newline="",
) as file:
    records = list(csv.DictReader(file))


TRAFFIC_BILLING_MAP = {
    "prepaid": "DC_PREPAD",
    "hybrid": "DC_HYBRID",
    "total": "DC_TOTAL",
}

TrafficMetric = Literal["DC_TOTAL", "DC_PREPAD", "DC_HYBRID"]

BillingType = Literal["prepaid", "hybrid", "total"]


KPIType = Literal[
    "Voice Traffic - Billed",
    "Voice Traffic - Free",
    "Voice Traffic - OOB",
    "Data Traffic - Billed",
    "Data Traffic - Free",
    "Data Traffic - OOB",
    "Sms Traffic - Billed",
    "Sms Traffic - Free",
    "Sms Traffic - OOB",
    "M-Pesa Paybill",
    "M-Pesa P2P",
    "M-Pesa Withdrawal",
    "M-Pesa Others",
    "Interconnect Local - Movitel",
    "Interconnect Local - mCel",
    "Interconnect Local - TDM",
    "Interconnect International",
    "Inflows",
    "Outflows",
]


# Function to get total traffic per day for a specific KPI and date
def get_total_traffic_per_day(
    kpi: KPIType,
    date: str,
    billing_type: BillingType = "total",
) -> dict:
    """Calculates the total volume of network traffic for a specific KPI on a given date.

    Args:
        kpi: The traffic KPI to query (e.g., 'Voice Traffic - Billed', 'Data Traffic - Billed').
        date: The target date in 'DD-MMM-YY' uppercase format (e.g., '22-OCT-25').
        billing_type: The customer billing segment ('prepaid', 'hybrid', 'total').
          Defaults to 'total'.

    Returns:
        dict: A dictionary containing query metadata and formatted total traffic,
              or an error dictionary if processing fails.
    """
    try:
        target_column = TRAFFIC_BILLING_MAP.get(billing_type.lower(), billing_type)
        total = sum(
            float(item[target_column])
            for item in records
            if item.get("EVENT_DESCRIPTION") == kpi and item.get("DC_DATE") == date
        )

        return {
            "date": date,
            "kpi": kpi,
            "billing_type": billing_type,
            "total_traffic": f"{round(total):,}",
        }
    except (KeyError, ValueError) as e:
        return {"error": f"get_total_traffic_per_day failed due to invalid data: {e}"}


# Function to get the total traffic for a specific KPI and date range
def get_kpi_month_to_date_total(
    kpi: KPIType, target_date: str, billing_type: BillingType = "prepaid"
) -> dict:
    """Calculates the Month-To-Date (MTD) cumulative traffic for a specific KPI up to a target date.

    Args:
        kpi: The traffic KPI to accumulate (e.g., 'SMS Traffic - Billed', 'Total Traffic').
        target_date: The end date for the MTD period in 'DD-MMM-YY' format (e.g., '22-OCT-25').
        billing_type: The customer billing segment ('prepaid', 'hybrid', 'total').
          Defaults to 'prepaid'.

    Returns:
        dict: A dictionary with target date, KPI, billing type, and cumulative MTD traffic.
    """
    try:
        target_column = TRAFFIC_BILLING_MAP.get(billing_type.lower(), billing_type)
        parsed_dt = datetime.strptime(target_date, "%d-%b-%y").replace(tzinfo=UTC)
        target_date_obj = parsed_dt.date()
        month_start_date = target_date_obj.replace(day=1)
        month_to_date_total = 0.0

        for record in records:
            if record["EVENT_DESCRIPTION"] != kpi:
                continue

            record_date = (
                datetime.strptime(record["DC_DATE"], "%d-%b-%y")
                .replace(tzinfo=UTC)
                .date()
            )

            if month_start_date <= record_date <= target_date_obj:
                month_to_date_total += float(record.get(target_column))

        return {
            "date": target_date,
            "kpi": kpi,
            "billing_type": billing_type,
            "month_to_date_total": f"{round(month_to_date_total):,}",
        }

    except (KeyError, ValueError) as e:
        return {"error": f"get_kpi_month_to_date_total failed due to invalid data: {e}"}


# Function to get month-on-month metrics for a specific KPI and date
def get_traffic_month_on_month_metrics(
    kpi: KPIType, target_date: str, billing_type: BillingType = "prepaid"
) -> dict:
    """Compares Month-To-Date (MTD) traffic metrics between the target date and the same day of the previous month (MoM) for a KPI.

    Args:
        kpi: The traffic KPI to analyze (e.g., 'Voice Traffic - Billed', 'Data Traffic - Billed').
        target_date: The evaluation date in 'DD-MMM-YY' format (e.g., '22-OCT-25').
        billing_type: Customer billing segment ('prepaid', 'hybrid', 'total').
          Defaults to 'prepaid'.

    Returns:
        dict: Comparison metrics including current MTD total, previous month MTD total,
              absolute difference, and percentage change.
    """
    try:
        previous_month_date = get_previous_month_same_day(target_date)

        current_data = get_kpi_month_to_date_total(kpi, target_date, billing_type)
        previous_data = get_kpi_month_to_date_total(
            kpi, previous_month_date, billing_type
        )

        current_month_total = float(
            current_data.get("month_to_date_total", 0).replace(",", "")
        )
        previous_month_total = float(
            previous_data.get("month_to_date_total", 0).replace(",", "")
        )

        difference = current_month_total - previous_month_total

        percentage_change = (
            (difference / previous_month_total) * 100
            if previous_month_total != 0
            else None
        )

        return {
            "target_date": target_date,
            "previous_month_date": previous_month_date,
            "kpi": kpi,
            "billing_type": billing_type,
            "current_month_total": f"{round(current_month_total):,}",
            "previous_month_total": f"{round(previous_month_total):,}",
            "difference": f"{round(difference):,}",
            "percentage_change": (
                round(percentage_change, 1) if percentage_change is not None else None
            ),
        }
    except (KeyError, ValueError, TypeError) as e:
        return {
            "error": (
                f"get_traffic_month_on_month_metrics failed due to invalid data: {e}"
            )
        }


# Function to get year-on-year metrics for a specific KPI and date
def get_traffic_year_on_year_metrics(
    kpi: KPIType, target_date: str, billing_type: BillingType = "prepaid"
) -> dict:
    """Compares Month-To-Date (MTD) traffic metrics between the target date and the same day of the previous year (YoY) for a KPI.

    Args:
        kpi: The traffic KPI to analyze (e.g., 'Voice Traffic - Billed', 'Data Traffic - Billed').
        target_date: The evaluation date in 'DD-MMM-YY' format (e.g., '22-OCT-25').
        billing_type: Customer billing segment ('prepaid', 'hybrid', 'total').
          Defaults to 'prepaid'.

    Returns:
        dict: Comparison metrics including current year MTD total, previous year MTD total,
              absolute difference, and percentage change.
    """
    try:
        previous_year_date = get_previous_year_same_day(target_date)
        current_data = get_kpi_month_to_date_total(kpi, target_date, billing_type)
        previous_data = get_kpi_month_to_date_total(
            kpi, previous_year_date, billing_type
        )

        current_year_total = float(
            current_data.get("month_to_date_total", 0).replace(",", "")
        )
        previous_year_total = float(
            previous_data.get("month_to_date_total", 0).replace(",", "")
        )

        difference = current_year_total - previous_year_total
        percentage_change = (
            (difference / previous_year_total) * 100
            if previous_year_total != 0
            else None
        )

        return {
            "target_date": target_date,
            "previous_year_date": previous_year_date,
            "kpi": kpi,
            "billing_type": billing_type,
            "current_year_total": f"{round(current_year_total):,}",
            "previous_year_total": f"{round(previous_year_total):,}",
            "difference": f"{round(difference):,}",
            "percentage_change": (
                round(percentage_change, 1) if percentage_change is not None else None
            ),
        }
    except (KeyError, ValueError, TypeError) as e:
        return {
            "error": (
                f"get_traffic_year_on_year_metrics failed due to invalid data: {e}"
            )
        }


# Function to get the same day of the previous month for a given date
def get_previous_month_same_day(target_date: str) -> str:
    try:
        target_date_obj = (
            datetime.strptime(target_date, "%d-%b-%y").replace(tzinfo=UTC).date()
        )
        prev_month_date = target_date_obj - relativedelta(months=1)
        return prev_month_date.strftime("%d-%b-%y").upper()
    except ValueError as e:
        raise ValueError(
            f"Data inválida '{target_date}'. O formato esperado é 'DD-MMM-YY' (ex: '22-OCT-25')."
        ) from e


# Function to get the same day of the previous year for a given date
def get_previous_year_same_day(target_date: str) -> str:
    try:
        target_date_obj = (
            datetime.strptime(target_date, "%d-%b-%y").replace(tzinfo=UTC).date()
        )
        prev_year_date = target_date_obj - relativedelta(years=1)
        return prev_year_date.strftime("%d-%b-%y").upper()
    except ValueError as e:
        raise ValueError(
            f"Data inválida '{target_date}'. O formato esperado é 'DD-MMM-YY' (ex: '22-OCT-25')."
        ) from e
