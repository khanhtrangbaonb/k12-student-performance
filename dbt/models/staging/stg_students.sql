-- Cleaned, typed student records. One row per student.
with source as (
    select * from {{ source('raw', 'students') }}
)
select
    student_id,
    initcap(first_name)                 as first_name,
    initcap(last_name)                  as last_name,
    cast(grade_level as integer)        as grade_level,
    school_id,
    upper(gender)                       as gender,
    cast(ell_flag as boolean)           as is_ell,
    cast(iep_flag as boolean)           as has_iep,
    cast(frl_flag as boolean)           as is_frl
from source
