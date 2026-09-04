with source as (

    select *
    from {{ source('raw', 'national_roaming') }}

),

renamed as (

    select
        cast(event_date as date)          as event_date,
        cast(country as varchar)          as country,
        cast(partner_network as varchar)  as partner_network,
        cast(revenue as numeric(18, 2))   as revenue,
        cast(duration as numeric(18, 2))  as duration,
        cast(total_mb as numeric(18, 2))  as total_mb
    from source
    where event_date is not null

)

select *
from renamed
