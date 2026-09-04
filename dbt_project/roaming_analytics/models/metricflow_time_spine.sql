-- Required by the dbt Semantic Layer / MetricFlow: a daily time spine used to
-- resolve time-based joins for metrics defined in models/metrics/metrics.yml.
{{ config(materialized='table') }}

select
    cast(day_date as date) as date_day
from (
    select generate_series(
        cast('2020-01-01' as date),
        cast('2035-12-31' as date),
        interval '1 day'
    ) as day_date
) as spine
