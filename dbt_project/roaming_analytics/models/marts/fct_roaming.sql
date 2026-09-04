with staged as (

    select *
    from {{ ref('stg_national_roaming') }}

)

select
    md5(
        cast(event_date as varchar) || '-' ||
        country || '-' ||
        partner_network || '-' ||
        cast(revenue as varchar) || '-' ||
        cast(duration as varchar) || '-' ||
        cast(total_mb as varchar)
    ) as roaming_event_id,
    event_date,
    country,
    partner_network,
    revenue,
    duration,
    total_mb
from staged
