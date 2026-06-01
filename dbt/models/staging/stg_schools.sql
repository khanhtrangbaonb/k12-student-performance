-- School master with district rollup.
with source as (
    select * from {{ source('raw', 'schools') }}
)
select
    school_id,
    school_name,
    district_id,
    district_name,
    school_level
from source
