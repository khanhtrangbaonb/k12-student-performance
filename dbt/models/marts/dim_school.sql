-- School dimension with district attributes for drill paths.
select
    school_id,
    school_name,
    district_id,
    district_name,
    school_level
from {{ ref('stg_schools') }}
