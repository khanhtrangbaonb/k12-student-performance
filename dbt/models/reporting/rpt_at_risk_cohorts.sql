-- At-risk roster: students in Intervention / Urgent Intervention in the most
-- recent (Spring) window, prioritised by decline and support needs.
with f as (select * from {{ ref('fct_assessment_results') }}),
g as (select * from {{ ref('rpt_student_growth') }}),
stu as (select * from {{ ref('dim_student') }}),
sch as (select * from {{ ref('dim_school') }}),
spring as (
    select student_id, subject_id, scaled_score, percentile_rank, benchmark_category
    from f where window_id = 'W3'
)
select
    stu.student_id,
    stu.student_name,
    stu.grade_label,
    sch.district_name,
    sch.school_name,
    sp.subject_id,
    sp.scaled_score        as spring_score,
    sp.percentile_rank     as spring_pr,
    sp.benchmark_category,
    g.scaled_growth,
    g.growth_flag,
    stu.is_ell,
    stu.has_iep,
    stu.is_frl,
    -- priority score: lower percentile + declining + support need => higher
    ( (40 - least(sp.percentile_rank, 40))
      + case when g.scaled_growth < 0 then 25 else 0 end
      + case when stu.has_support_need then 10 else 0 end ) as priority_score
from spring sp
join stu on sp.student_id = stu.student_id
join sch on stu.school_id = sch.school_id
left join g on sp.student_id = g.student_id and sp.subject_id = g.subject_id
where sp.benchmark_category in ('Intervention', 'Urgent Intervention')
