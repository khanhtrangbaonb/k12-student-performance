select distinct
    subject_id,
    subject_name
from {{ ref('stg_assessments') }}
