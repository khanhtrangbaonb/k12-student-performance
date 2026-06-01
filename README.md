# K–12 Student Performance Analytics Pipeline

An end-to-end **business intelligence / analytics-engineering** project: raw
benchmark-assessment extracts are modeled into a **dbt star schema**, validated
with **data-quality tests**, and surfaced through an interactive **dashboard**
that lets stakeholders drill from district → school → grade → student.

The dataset is **synthetic** (generated locally, no real student records) but is
shaped like a NYC DoE trimester benchmark program — three windows per year
(Fall / Winter / Spring), scaled scores, percentile ranks, and benchmark
categories (At/Above Benchmark, On Watch, Intervention, Urgent Intervention).
---
## Adapting to production (real) data

This repo runs on **synthetic** data on purpose. Real K–12 assessment records
are FERPA-protected education records — names, scores, and especially the
IEP / ELL / free-and-reduced-lunch flags are sensitive — so they must never be
committed to a repository (public *or* private). The synthetic dataset exists
so the modeling, testing, and dashboards can be shown publicly without exposing
anyone.

To run the same project against real data inside a sanctioned environment
(a school/district warehouse), the engineering grows in a few predictable ways:

- **Swap the sources.** Point dbt's `sources` at the real Star / eSD / SIS
  extracts landing in Snowflake instead of the CSVs. The staging layer is where
  real-world schema differences get absorbed.
- **Harden for messiness.** Real data has nulls, duplicate enrollments,
  mid-year school transfers, late-arriving results, and drifting column names.
  The `not_null` / `unique` / `relationships` tests start catching genuine
  issues rather than confirming a clean demo.
- **Track history with snapshots.** Students change grade, school, and support
  flags over time — model `dim_student` as a slowly-changing dimension via dbt
  snapshots so results can be read "as of" a given window.
- **Go incremental.** Convert `fct_assessment_results` to an incremental model
  once the history spans many windows and years, so runs stay fast.
- **Control access.** Use warehouse roles so student-level rows are restricted
  while dashboards expose only aggregates, and enforce minimum cell sizes in
  reporting marts to prevent re-identification.
---

## What it demonstrates

| Skill from the BI job description | Where it shows up |
|---|---|
| Building & maintaining **data models** | `dbt/models/marts/` — conformed star schema |
| **Data modeling concepts** / dbt | dbt project with sources, staging, marts, reporting, tests |
| **Dashboards** for decision-making | `dashboard/index.html` (drill-down BI dashboard) |
| Exploring data for **trends & anomalies** | proficiency trend, growth flags, at-risk roster |
| **Data quality** & attention to detail | 9 schema tests (unique / not_null / relationships / range / accepted_values) |
| **Snowflake / cloud warehouse** | `profiles.yml` ships a Snowflake target alongside DuckDB |
| **Python / AI-assisted workflows** | data generation + pipeline runner in Python |
| Communicating to **non-technical stakeholders** | dashboard KPIs + plain-language at-risk roster |

---

## Architecture

```
 raw CSVs (sources)          dbt models                          consumption
 ─────────────────     ───────────────────────────────────     ─────────────
 students.csv ─┐       staging/ (views, typed & cleaned)
 schools.csv ──┤  ──▶  stg_students / stg_schools / stg_assess
 assessment ───┤                     │
 _results.csv  │       marts/ (star schema, tables)
 windows.csv ──┤  ──▶  dim_student  dim_school  dim_subject
 subjects.csv ─┘       dim_window   fct_assessment_results
                                     │
                       reporting/ (curated BI tables)
                       rpt_proficiency_trends                  ──▶ dashboard/
                       rpt_student_growth                          index.html
                       rpt_at_risk_cohorts
```

**Grain of the fact table:** one row per *student × subject × benchmark window*.

---

## Run it

### Option A — the real dbt pipeline (recommended for the portfolio)

```bash
pip install dbt-duckdb            # free, local, no warehouse needed
python data/generate_data.py      # writes raw CSVs
cd dbt
dbt build                         # runs all models + all data-quality tests
```

`dbt build` materializes the staging views, the star-schema marts, and the
reporting tables, then runs every test in the `schema.yml` files. To run the
identical project on a real warehouse:

```bash
dbt build --target snowflake      # uses the snowflake target in profiles.yml
```

### Option B — local runner (no dbt install required)

`run_pipeline.py` executes the same transformation + test logic in pandas and
writes the modeled tables to `output/` plus the JSON the dashboard reads:

```bash
python data/generate_data.py
python run_pipeline.py
```

### View the dashboard

Open `dashboard/index.html` in any browser — it's fully self-contained
(data embedded, no server, no internet needed). Use the District and Subject
filters; click rows in the drill-down to expand district → school → grade.

---

## Rebuilding the dashboard in Power BI

The dashboard here is vanilla SVG so it runs anywhere, but the same model drops
straight into Power BI:

1. `python run_pipeline.py` (or `dbt build`) to produce the tables in `output/`.
2. In Power BI Desktop: **Get Data → Text/CSV** and load the `dim_*`, `fct_*`,
   and `rpt_*` files (or connect directly to DuckDB/Snowflake).
3. In **Model view**, the keys are already named for a star schema — relate
   `fct_assessment_results` to each `dim_*` on the matching id.
4. Build visuals: a line chart on `rpt_proficiency_trends` (window vs
   % proficient), a 100%-stacked column for benchmark mix, a matrix on
   district/school/grade for drill-down, and a table on `rpt_at_risk_cohorts`
   sorted by `priority_score`.

---

## Repo layout

```
k12-student-performance-bi/
├── README.md
├── requirements.txt
├── data/
│   ├── generate_data.py        # synthetic source generator
│   └── raw/                    # generated source CSVs
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml            # DuckDB + Snowflake targets
│   └── models/
│       ├── staging/            # stg_* + source defs + tests
│       ├── marts/              # dim_* + fct_* (star schema) + tests
│       └── reporting/          # rpt_* BI tables
├── run_pipeline.py             # pandas executor + test harness
├── output/                     # modeled tables + dashboard_data.json
└── dashboard/
    └── index.html              # interactive BI dashboard
```
