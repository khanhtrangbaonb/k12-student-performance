-- Typed assessment results joined to window + subject labels.
with results as (
    select * from {{ source('raw', 'assessment_results') }}
),
windows as (
    select * from {{ source('raw', 'benchmark_windows') }}
),
subjects as (
    select * from {{ source('raw', 'subjects') }}
)
select
    r.result_id,
    r.student_id,
    r.subject_id,
    s.subject_name,
    r.window_id,
    w.window_label,
    cast(w.window_sort as integer)      as window_sort,
    cast(w.test_date as date)           as test_date,
    r.school_year,
    cast(r.scaled_score as double)      as scaled_score,
    cast(r.percentile_rank as integer)  as percentile_rank,
    r.benchmark_category
from results r
left join windows  w on r.window_id  = w.window_id
left join subjects s on r.subject_id = s.subject_id
