-- Proficiency distribution by district / school / grade / subject / window.
-- Feeds the dashboard's trend lines and benchmark-mix bars.
with f as (select * from {{ ref('fct_assessment_results') }}),
sch as (select * from {{ ref('dim_school') }}),
stu as (select * from {{ ref('dim_student') }}),
w   as (select * from {{ ref('dim_window') }})
select
    sch.district_name,
    sch.school_id,
    sch.school_name,
    stu.grade_label,
    f.subject_id,
    w.window_label,
    w.window_sort,
    count(*)                                          as n_assessments,
    round(avg(f.scaled_score), 1)                     as avg_scaled_score,
    round(avg(f.percentile_rank), 1)                  as avg_percentile,
    round(100.0 * avg(case when f.is_proficient then 1 else 0 end), 1) as pct_proficient,
    round(100.0 * avg(case when f.is_at_risk    then 1 else 0 end), 1) as pct_at_risk
from f
join sch on f.school_id = sch.school_id
join stu on f.student_id = stu.student_id
join w   on f.window_id  = w.window_id
group by 1,2,3,4,5,6,7
