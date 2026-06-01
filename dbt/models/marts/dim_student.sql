-- Student dimension. Conformed grain: one row per student.
with s as (select * from {{ ref('stg_students') }})
select
    student_id,
    first_name,
    last_name,
    first_name || ' ' || last_name as student_name,
    grade_level,
    case
        when grade_level = 0 then 'K'
        else cast(grade_level as varchar)
    end as grade_label,
    school_id,
    gender,
    is_ell,
    has_iep,
    is_frl,
    -- composite "support needs" flag used by at-risk reporting
    (is_ell or has_iep or is_frl) as has_support_need
from s
