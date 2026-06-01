"""
run_pipeline.py
---------------
Local executor that runs the SAME logic as the dbt models against the raw
CSVs, runs the data-quality tests, and writes the modeled tables + a compact
JSON the dashboard reads.

This exists so the project is verifiable end-to-end without a warehouse.
On a real machine you would instead run:

    pip install dbt-duckdb
    cd dbt && dbt deps && dbt build      # builds models + runs all tests

Both paths produce identical tables.

Run:  python run_pipeline.py
"""
import json
import os
import sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- load raw
students_raw   = pd.read_csv(f"{RAW}/students.csv")
schools_raw    = pd.read_csv(f"{RAW}/schools.csv")
results_raw    = pd.read_csv(f"{RAW}/assessment_results.csv")
windows_raw    = pd.read_csv(f"{RAW}/benchmark_windows.csv")
subjects_raw   = pd.read_csv(f"{RAW}/subjects.csv")

# ---------------------------------------------------------------- staging
stg_students = students_raw.rename(columns={
    "ell_flag": "is_ell", "iep_flag": "has_iep", "frl_flag": "is_frl"
}).copy()

stg_schools = schools_raw.copy()

stg_assess = (results_raw
    .merge(windows_raw, on="window_id", how="left")
    .merge(subjects_raw, on="subject_id", how="left"))

# ---------------------------------------------------------------- marts (star schema)
dim_student = stg_students.copy()
dim_student["student_name"] = dim_student["first_name"] + " " + dim_student["last_name"]
dim_student["grade_label"] = dim_student["grade_level"].apply(lambda g: "K" if g == 0 else str(g))
dim_student["has_support_need"] = dim_student[["is_ell", "has_iep", "is_frl"]].any(axis=1)

dim_school = stg_schools.copy()
dim_subject = stg_assess[["subject_id", "subject_name"]].drop_duplicates()
dim_window = stg_assess[["window_id", "window_label", "window_sort", "test_date",
                         "school_year"]].drop_duplicates()

fct = stg_assess.merge(dim_student[["student_id", "school_id"]], on="student_id", how="left")
fct["is_proficient"] = fct["benchmark_category"].eq("At/Above Benchmark")
fct["is_at_risk"] = fct["benchmark_category"].isin(["Intervention", "Urgent Intervention"])
fct = fct[["result_id", "student_id", "school_id", "subject_id", "window_id", "window_sort",
           "school_year", "scaled_score", "percentile_rank", "benchmark_category",
           "is_proficient", "is_at_risk"]]

# ---------------------------------------------------------------- reporting marts
sm = (fct.merge(dim_school, on="school_id")
      .merge(dim_student[["student_id", "grade_label", "student_name", "has_support_need",
                          "is_ell", "has_iep", "is_frl"]], on="student_id")
      .merge(dim_window[["window_id", "window_label"]], on="window_id"))

rpt_prof = (sm.groupby(["district_name", "school_id", "school_name", "grade_label",
                        "subject_id", "window_label", "window_sort"], as_index=False)
    .agg(n_assessments=("result_id", "count"),
         avg_scaled_score=("scaled_score", "mean"),
         avg_percentile=("percentile_rank", "mean"),
         pct_proficient=("is_proficient", "mean"),
         pct_at_risk=("is_at_risk", "mean")))
rpt_prof["avg_scaled_score"] = rpt_prof["avg_scaled_score"].round(1)
rpt_prof["avg_percentile"] = rpt_prof["avg_percentile"].round(1)
rpt_prof["pct_proficient"] = (rpt_prof["pct_proficient"] * 100).round(1)
rpt_prof["pct_at_risk"] = (rpt_prof["pct_at_risk"] * 100).round(1)

fall = fct[fct.window_id == "W1"][["student_id", "subject_id", "scaled_score",
                                   "percentile_rank", "benchmark_category"]].rename(
    columns={"scaled_score": "fall_score", "percentile_rank": "fall_pr",
             "benchmark_category": "fall_band"})
spring = fct[fct.window_id == "W3"][["student_id", "subject_id", "scaled_score",
                                     "percentile_rank", "benchmark_category"]].rename(
    columns={"scaled_score": "spring_score", "percentile_rank": "spring_pr",
             "benchmark_category": "spring_band"})

g = fall.merge(spring, on=["student_id", "subject_id"]).merge(
    dim_student[["student_id", "student_name", "grade_label", "school_id"]], on="student_id").merge(
    dim_school[["school_id", "district_name", "school_name"]], on="school_id")
g["scaled_growth"] = (g["spring_score"] - g["fall_score"]).round(1)
g["percentile_change"] = g["spring_pr"] - g["fall_pr"]

def growth_flag(x):
    if x >= 30: return "Strong Growth"
    if x >= 10: return "On Track"
    if x >= -5: return "Flat"
    return "Declining"
g["growth_flag"] = g["scaled_growth"].apply(growth_flag)
rpt_growth = g[["student_id", "student_name", "grade_label", "district_name", "school_name",
                "subject_id", "fall_score", "spring_score", "scaled_growth",
                "percentile_change", "fall_band", "spring_band", "growth_flag"]]

at_risk = spring.merge(
    dim_student[["student_id", "student_name", "grade_label", "school_id",
                 "is_ell", "has_iep", "is_frl", "has_support_need"]], on="student_id").merge(
    dim_school[["school_id", "district_name", "school_name"]], on="school_id").merge(
    rpt_growth[["student_id", "subject_id", "scaled_growth", "growth_flag"]],
    on=["student_id", "subject_id"], how="left")
at_risk = at_risk[at_risk.spring_band.isin(["Intervention", "Urgent Intervention"])].copy()
at_risk["priority_score"] = (
    (40 - at_risk["spring_pr"].clip(upper=40))
    + at_risk["scaled_growth"].lt(0).mul(25)
    + at_risk["has_support_need"].mul(10)).astype(int)
rpt_at_risk = at_risk[["student_id", "student_name", "grade_label", "district_name",
                       "school_name", "subject_id", "spring_score", "spring_pr",
                       "spring_band", "scaled_growth", "growth_flag",
                       "is_ell", "has_iep", "is_frl", "priority_score"]].rename(
    columns={"spring_band": "benchmark_category"})

# ---------------------------------------------------------------- DATA QUALITY TESTS
failures = []

def test(name, condition):
    ok = bool(condition)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        failures.append(name)

print("\nRunning data-quality tests (mirrors dbt schema.yml tests):")
test("unique: dim_student.student_id", dim_student.student_id.is_unique)
test("not_null: dim_student.student_id", dim_student.student_id.notna().all())
test("unique: fct.result_id", fct.result_id.is_unique)
test("not_null: fct.scaled_score", fct.scaled_score.notna().all())
test("accepted_range: scaled_score 0-1500",
     fct.scaled_score.between(0, 1500).all())
test("accepted_values: benchmark_category",
     fct.benchmark_category.isin(['At/Above Benchmark', 'On Watch',
                                  'Intervention', 'Urgent Intervention']).all())
test("relationships: fct.student_id -> dim_student",
     fct.student_id.isin(dim_student.student_id).all())
test("relationships: fct.school_id -> dim_school",
     fct.school_id.isin(dim_school.school_id).all())
test("accepted_values: grade_level 0-8",
     stg_students.grade_level.between(0, 8).all())

# ---------------------------------------------------------------- write outputs
tables = {
    "dim_student": dim_student, "dim_school": dim_school, "dim_subject": dim_subject,
    "dim_window": dim_window, "fct_assessment_results": fct,
    "rpt_proficiency_trends": rpt_prof, "rpt_student_growth": rpt_growth,
    "rpt_at_risk_cohorts": rpt_at_risk,
}
for nm, df in tables.items():
    df.to_csv(f"{OUT}/{nm}.csv", index=False)

# ---------------------------------------------------------------- dashboard JSON
subj_map = dict(zip(subjects_raw.subject_id, subjects_raw.subject_name))

def f1(x):  # round helper
    return round(float(x), 1)

# overall KPIs (Spring)
spring_fct = fct[fct.window_id == "W3"]
dash = {
    "meta": {
        "school_year": "2024-2025",
        "n_students": int(dim_student.student_id.nunique()),
        "n_schools": int(dim_school.school_id.nunique()),
        "n_districts": int(dim_school.district_name.nunique()),
        "n_assessments": int(len(fct)),
        "subjects": subj_map,
    },
    "kpis": {
        "pct_proficient_spring": f1(100 * spring_fct.is_proficient.mean()),
        "pct_at_risk_spring": f1(100 * spring_fct.is_at_risk.mean()),
        "avg_growth": f1(rpt_growth.scaled_growth.mean()),
        "pct_strong_growth": f1(100 * rpt_growth.growth_flag.eq("Strong Growth").mean()),
    },
    # proficiency trend by window, district, subject
    "trends": rpt_prof.groupby(
        ["district_name", "subject_id", "window_label", "window_sort"], as_index=False
        ).agg(pct_proficient=("pct_proficient", "mean"),
              avg_scaled_score=("avg_scaled_score", "mean"),
              pct_at_risk=("pct_at_risk", "mean")).round(1).to_dict("records"),
    # benchmark mix by window (district level) for stacked bars
    "benchmark_mix": [],
    # district -> school -> grade rollup for the drill-down table
    "drill": [],
    "growth_flags": rpt_growth.groupby(["district_name", "subject_id", "growth_flag"],
        as_index=False).size().rename(columns={"size": "n"}).to_dict("records"),
    "at_risk_top": rpt_at_risk.sort_values("priority_score", ascending=False)
        .head(40).round(1).to_dict("records"),
}

mix = (sm[sm.window_id.isin(["W1", "W2", "W3"])]
       .groupby(["district_name", "subject_id", "window_label", "window_sort",
                 "benchmark_category"], as_index=False).size())
dash["benchmark_mix"] = mix.rename(columns={"size": "n"}).to_dict("records")

drill = (sm[sm.window_id == "W3"].groupby(
    ["district_name", "school_name", "grade_label", "subject_id"], as_index=False)
    .agg(n=("result_id", "count"),
         pct_proficient=("is_proficient", "mean"),
         pct_at_risk=("is_at_risk", "mean"),
         avg_scaled=("scaled_score", "mean")))
drill["pct_proficient"] = (drill.pct_proficient * 100).round(1)
drill["pct_at_risk"] = (drill.pct_at_risk * 100).round(1)
drill["avg_scaled"] = drill.avg_scaled.round(0)
dash["drill"] = drill.to_dict("records")

with open(f"{OUT}/dashboard_data.json", "w") as fh:
    json.dump(dash, fh, separators=(",", ":"))

print("\nModeled tables written to output/:")
for nm, df in tables.items():
    print(f"  {nm:<28} {len(df):>6} rows")
print(f"\nDashboard data -> output/dashboard_data.json")

if failures:
    print(f"\n{len(failures)} TEST(S) FAILED")
    sys.exit(1)
print("\nAll data-quality tests PASSED.")
