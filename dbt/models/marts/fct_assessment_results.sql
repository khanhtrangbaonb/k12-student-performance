-- Central fact table. Grain: one row per student / subject / benchmark window.
-- Foreign keys point at the conformed dimensions above.
with a as (select * from {{ ref('stg_assessments') }}),
stu as (select student_id, school_id from {{ ref('dim_student') }})
select
    a.result_id,
    a.student_id,
    stu.school_id,
    a.subject_id,
    a.window_id,
    a.window_sort,
    a.school_year,
    a.scaled_score,
    a.percentile_rank,
    a.benchmark_category,
    -- proficiency boolean for fast aggregate measures
    (a.benchmark_category = 'At/Above Benchmark') as is_proficient,
    (a.benchmark_category in ('Intervention', 'Urgent Intervention')) as is_at_risk
from a
left join stu on a.student_id = stu.student_id
