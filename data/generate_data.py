"""
generate_data.py
----------------
Generates realistic, synthetic K-12 benchmark-assessment data and writes it to
data/raw/ as CSVs. These CSVs are the *raw sources* the dbt project reads from.

No real student data is used. The structure mirrors a Renaissance-style
benchmark assessment program (e.g. Star Reading / Star Math) with three
benchmark windows per year (Fall, Winter, Spring), scaled scores, percentile
ranks, and benchmark categories (At/Above Benchmark, On Watch,
Intervention, Urgent Intervention).

Run:  python data/generate_data.py
"""

import os
import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)          # reproducible
OUT = os.path.join(os.path.dirname(__file__), "raw")
os.makedirs(OUT, exist_ok=True)

SCHOOL_YEAR = "2024-2025"

# ----------------------------------------------------------------------------
# 1. Districts & schools
# ----------------------------------------------------------------------------
DISTRICTS = [
    ("D01", "Riverside Unified"),
    ("D02", "Lakewood Public"),
    ("D03", "Hillcrest Community"),
]

SCHOOL_DEFS = [
    # (school_id, name, district_id, level, grades, n_students)
    ("S001", "Maple Grove Elementary", "D01", "Elementary", (0, 5), 420),
    ("S002", "Oak Ridge Elementary",   "D01", "Elementary", (0, 5), 380),
    ("S003", "Riverside Middle",       "D01", "Middle",     (6, 8), 510),
    ("S004", "Birchwood Elementary",   "D02", "Elementary", (0, 5), 350),
    ("S005", "Lakewood Middle",        "D02", "Middle",     (6, 8), 470),
    ("S006", "Cedar Point Elementary", "D03", "Elementary", (0, 5), 300),
    ("S007", "Hillcrest Middle",       "D03", "Middle",     (6, 8), 440),
]

WINDOWS = [
    # (window_id, label, sort, test_date)
    ("W1", "Fall",   1, "2024-09-20"),
    ("W2", "Winter", 2, "2025-01-17"),
    ("W3", "Spring", 3, "2025-05-09"),
]

SUBJECTS = [("SUBJ_R", "Reading"), ("SUBJ_M", "Math")]

FIRST = ["Avery","Jordan","Riley","Casey","Morgan","Quinn","Skyler","Devon","Rowan","Sage",
         "Emery","Reese","Finley","Harper","Jamie","Kai","Logan","Micah","Noa","Parker"]
LAST  = ["Nguyen","Garcia","Smith","Johnson","Patel","Kim","Lopez","Brown","Davis","Martinez",
         "Lee","Wilson","Anderson","Thomas","Khan","Rivera","Chen","Walker","Young","Hill"]


def benchmark_category(pr):
    """Map a percentile rank to a Renaissance-style benchmark category."""
    if pr >= 40:
        return "At/Above Benchmark"
    if pr >= 25:
        return "On Watch"
    if pr >= 10:
        return "Intervention"
    return "Urgent Intervention"


def main():
    # --- schools ---
    schools = []
    for sid, name, did, level, grades, n in SCHOOL_DEFS:
        dname = dict(DISTRICTS)[did]
        schools.append(dict(school_id=sid, school_name=name, district_id=did,
                            district_name=dname, school_level=level))
    pd.DataFrame(schools).to_csv(f"{OUT}/schools.csv", index=False)

    # --- students ---
    students = []
    sid_counter = 1
    for sid, name, did, level, (gmin, gmax), n in SCHOOL_DEFS:
        for _ in range(n):
            grade = int(RNG.integers(gmin, gmax + 1))
            students.append(dict(
                student_id=f"STU{sid_counter:05d}",
                first_name=RNG.choice(FIRST),
                last_name=RNG.choice(LAST),
                grade_level=grade,
                school_id=sid,
                gender=RNG.choice(["F", "M", "X"], p=[0.49, 0.49, 0.02]),
                ell_flag=bool(RNG.random() < 0.16),          # English language learner
                iep_flag=bool(RNG.random() < 0.13),          # has IEP
                frl_flag=bool(RNG.random() < 0.52),          # free/reduced lunch
            ))
            sid_counter += 1
    students_df = pd.DataFrame(students)
    students_df.to_csv(f"{OUT}/students.csv", index=False)

    # --- windows / subjects ---
    pd.DataFrame(WINDOWS, columns=["window_id", "window_label", "window_sort", "test_date"]
                 ).to_csv(f"{OUT}/benchmark_windows.csv", index=False)
    pd.DataFrame(SUBJECTS, columns=["subject_id", "subject_name"]
                 ).to_csv(f"{OUT}/subjects.csv", index=False)

    # --- assessment results (the raw fact feed) ---
    # Each student has a latent "true ability" per subject that drifts upward
    # across windows (learning) with noise; some students stagnate or decline.
    rows = []
    result_id = 1
    for s in students:
        grade = s["grade_level"]
        # base scaled score scales with grade; reading & math have own baselines
        for subj_id, subj_name in SUBJECTS:
            base = 250 + grade * 95 + RNG.normal(0, 120)
            # subject offset
            base += (30 if subj_name == "Reading" else -10)
            # at-risk students (ELL/IEP/FRL) skew lower
            base -= (60 if s["ell_flag"] else 0)
            base -= (50 if s["iep_flag"] else 0)
            base -= (25 if s["frl_flag"] else 0)

            # growth trajectory: most grow, ~18% flat/decline
            traj = RNG.choice(["grow", "flat", "decline"], p=[0.66, 0.16, 0.18])
            step = {"grow": RNG.normal(45, 18),
                    "flat": RNG.normal(5, 12),
                    "decline": RNG.normal(-28, 15)}[traj]

            for i, (wid, wlabel, wsort, tdate) in enumerate(WINDOWS):
                scaled = base + step * i + RNG.normal(0, 25)
                scaled = float(np.clip(scaled, 50, 1400))
                # percentile rank derived from scaled vs grade-expected
                expected = 250 + grade * 95 + 30 if subj_name == "Reading" else 250 + grade * 95 - 10
                z = (scaled - expected) / 160.0
                pr = int(np.clip(round(50 + z * 22 + RNG.normal(0, 5)), 1, 99))
                rows.append(dict(
                    result_id=f"R{result_id:07d}",
                    student_id=s["student_id"],
                    subject_id=subj_id,
                    window_id=wid,
                    school_year=SCHOOL_YEAR,
                    scaled_score=round(scaled, 1),
                    percentile_rank=pr,
                    benchmark_category=benchmark_category(pr),
                ))
                result_id += 1

    pd.DataFrame(rows).to_csv(f"{OUT}/assessment_results.csv", index=False)

    print(f"Wrote raw sources to {OUT}/")
    print(f"  schools.csv            {len(schools):>6} rows")
    print(f"  students.csv           {len(students):>6} rows")
    print(f"  assessment_results.csv {len(rows):>6} rows")
    print(f"  benchmark_windows.csv  {len(WINDOWS):>6} rows")
    print(f"  subjects.csv           {len(SUBJECTS):>6} rows")


if __name__ == "__main__":
    main()
