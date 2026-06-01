-- Benchmark-window (date) dimension.
select distinct
    window_id,
    window_label,
    window_sort,
    test_date,
    school_year
from {{ ref('stg_assessments') }}
