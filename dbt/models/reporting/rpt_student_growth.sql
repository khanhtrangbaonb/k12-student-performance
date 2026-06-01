-- Fall -> Spring growth per student / subject.
-- Growth = Spring scaled score minus Fall scaled score.
with f as (select * from {{ ref('fct_assessment_results') }}),
fall as (
    select student_id, subject_id, scaled_score as fall_score, percentile_rank as fall_pr,
           benchmark_category as fall_band
    from f where window_id = 'W1'
),
spring as (
    select student_id, subject_id, scaled_score as spring_score, percentile_rank as spring_pr,
           benchmark_category as spring_band
    from f where window_id = 'W3'
),
stu as (select * from {{ ref('dim_student') }}),
sch as (select * from {{ ref('dim_school') }})
select
    stu.student_id,
    stu.student_name,
    stu.grade_label,
    sch.district_name,
    sch.school_name,
    fall.subject_id,
    fall.fall_score,
    spring.spring_score,
    round(spring.spring_score - fall.fall_score, 1) as scaled_growth,
    spring.spring_pr - fall.fall_pr                 as percentile_change,
    fall.fall_band,
    spring.spring_band,
    case
        when spring.spring_score - fall.fall_score >= 30 then 'Strong Growth'
        when spring.spring_score - fall.fall_score >= 10 then 'On Track'
        when spring.spring_score - fall.fall_score >= -5 then 'Flat'
        else 'Declining'
    end as growth_flag
from fall
join spring on fall.student_id = spring.student_id and fall.subject_id = spring.subject_id
join stu on fall.student_id = stu.student_id
join sch on stu.school_id = sch.school_id
