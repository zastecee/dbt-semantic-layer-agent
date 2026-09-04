-- Executed automatically by the official postgres image on first container
-- start (mounted into /docker-entrypoint-initdb.d). Creates the raw table
-- consumed by the dbt staging model and loads the bundled sample dataset.

CREATE TABLE IF NOT EXISTS public.national_roaming (
    event_date      DATE           NOT NULL,
    country         VARCHAR(100)   NOT NULL,
    partner_network VARCHAR(150)   NOT NULL,
    revenue         NUMERIC(18, 2) NOT NULL,
    duration        NUMERIC(18, 2) NOT NULL,
    total_mb        NUMERIC(18, 2) NOT NULL
);

COPY public.national_roaming (event_date, country, partner_network, revenue, duration, total_mb)
FROM '/docker-entrypoint-initdb.d/roaming_data.csv'
WITH (FORMAT csv, HEADER true);

CREATE INDEX IF NOT EXISTS idx_national_roaming_event_date ON public.national_roaming (event_date);
CREATE INDEX IF NOT EXISTS idx_national_roaming_country ON public.national_roaming (country);
