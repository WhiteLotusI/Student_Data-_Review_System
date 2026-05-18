"""
Student Data Review System — Streamlit App
==========================================
Features:
  - Multi-file upload (process all 3 CSVs in one run)
  - Fuzzy column matching (tolerates typos / slight name differences)
  - Per-file status badges: Classified · Validated · Cleaned
  - Before / After view with highlighted changed cells
  - Export validation report as CSV
  - Upload history log (persisted in session)

Run locally:
    streamlit run app.py

Project layout:
    app.py                      ← root
    requirements.txt
    data/raw/   data/cleaned/
    scripts/
        cleaning_logic/  __init__.py  Student_*.py
        handlers/        __init__.py  error_handler.py
        logs/
        validation/      __init__.py  classifier.py  validator.py
"""

import sys, io, traceback, csv
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

# ── imports ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.cleaning_logic.Student_attendance  import clean_attendance_data
from scripts.cleaning_logic.Student_performance import clean_student_performance
from scripts.cleaning_logic.Student_profiles    import clean_student_profiles
from scripts.validation.validator import (
    validate_profiles,
    validate_performance,
    validate_attendance,
)

# ── directories ───────────────────────────────────────────────────────────────
for d in (ROOT/"data"/"raw", ROOT/"data"/"cleaned", ROOT/"scripts"/"logs"):
    d.mkdir(parents=True, exist_ok=True)

RAW_DIR = ROOT / "data" / "raw"

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Student Data Review",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1,h2,h3 { font-family: 'DM Serif Display', serif; }

.header-bar {
    background: linear-gradient(135deg,#0f2027,#203a43,#2c5364);
    padding: 2rem 2.5rem; border-radius:16px; margin-bottom:2rem; color:white;
}
.header-bar h1 { color:white; margin:0 0 .25rem 0; font-size:2rem; }
.header-bar p  { color:#a8c0cc; margin:0; font-size:1rem; }

.file-card {
    background:#1a2535; border:1px solid #2c4a5e;
    border-radius:12px; padding:1rem 1.25rem; margin-bottom:.75rem;
}
.file-card .fname { font-weight:600; color:#e2e8f0; font-size:.95rem; }
.file-card .fmeta { font-size:.8rem; color:#64748b; margin-top:.15rem; }

.badge {
    display:inline-block; padding:.18rem .65rem; border-radius:999px;
    font-size:.74rem; font-weight:600; letter-spacing:.04em; margin-right:.3rem;
}
.badge-profiles    { background:#dbeafe; color:#1e40af; }
.badge-performance { background:#dcfce7; color:#166534; }
.badge-attendance  { background:#fef9c3; color:#854d0e; }
.badge-unknown     { background:#fee2e2; color:#991b1b; }
.badge-ok          { background:#dcfce7; color:#166534; }
.badge-warn        { background:#fef9c3; color:#854d0e; }
.badge-err         { background:#fee2e2; color:#991b1b; }

.issue-item { padding:.4rem .75rem; border-radius:6px; margin:.25rem 0; font-size:.88rem; }
.issue-ok   { background:#dcfce7; color:#166534; }
.issue-warn { background:#fef9c3; color:#854d0e; }

.metric-box { background:#1e2d3d; border:1px solid #2c4a5e; border-radius:10px; padding:1rem; text-align:center; }
.metric-box .val { font-size:1.8rem; font-weight:700; color:#7dd3f0; }
.metric-box .lbl { font-size:.8rem; color:#94a3b8; margin-top:.2rem; }

.hist-row {
    display:flex; align-items:center; gap:.75rem;
    padding:.6rem .75rem; border-radius:8px;
    border:1px solid #2c4a5e; margin-bottom:.4rem;
    background:#1a2535; font-size:.85rem;
}
.hist-row .ht { color:#94a3b8; min-width:140px; }
.hist-row .hf { color:#e2e8f0; flex:1; }
.hist-row .hm { color:#64748b; font-size:.78rem; }

.step-card {
    background:#1e2d3d; border:1px solid #2c4a5e;
    border-left:4px solid #4a9bbe; border-radius:10px;
    padding:1rem 1.25rem; margin-bottom:.75rem; color:#e2e8f0;
}
.step-card b { color:#7dd3f0; }
.step-card small { color:#94a3b8; }
</style>
""", unsafe_allow_html=True)

# ── session state ─────────────────────────────────────────────────────────────
for key, default in [
    ("results",      []),   # list of per-file result dicts
    ("history",      []),   # upload history log
    ("last_names",   set()),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ═════════════════════════════════════════════════════════════════════════════
# FUZZY CLASSIFIER
# ═════════════════════════════════════════════════════════════════════════════

EXPECTED = {
    "profiles": {
        "student_id","student_name","class","gender","guardian_contact"
    },
    "performance": {
        "record_id","student_id","student_name","class","gender","term",
        "subject","attendance_percent","assignment_score","quiz_score",
        "exam_score","total_score","result","study_hours","teacher_comment"
    },
    "attendance": {
        "attendance_id","student_id","student_name","class","term",
        "days_present","days_absent","total_school_days","attendance_percent"
    },
}

def fuzzy_classify(df: pd.DataFrame):
    """
    Classify a dataframe by matching its columns against expected sets.
    Uses a similarity score (Jaccard) so minor column name differences
    or extra/missing columns don't break classification.
    Returns (dataset_type, score, missing_cols, extra_cols).
    Raises ValueError if best score < 0.55.
    """
    cols = set(df.columns.str.strip().str.lower().str.replace(" ", "_"))
    best_type, best_score, best_miss, best_extra = None, 0.0, set(), set()

    for dtype, expected in EXPECTED.items():
        intersection = cols & expected
        union        = cols | expected
        score        = len(intersection) / len(union) if union else 0
        if score > best_score:
            best_score = score
            best_type  = dtype
            best_miss  = expected - cols
            best_extra = cols - expected

    if best_score < 0.55:
        raise ValueError(
            f"No dataset type matched well enough "
            f"(best score {best_score:.0%}). "
            f"Columns found: {', '.join(sorted(cols))}"
        )
    return best_type, best_score, best_miss, best_extra


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════

BADGE_HTML = {
    "profiles":    '<span class="badge badge-profiles">👤 Profiles</span>',
    "performance": '<span class="badge badge-performance">📊 Performance</span>',
    "attendance":  '<span class="badge badge-attendance">📅 Attendance</span>',
}

VALIDATE_FN = {
    "profiles":    validate_profiles,
    "performance": validate_performance,
    "attendance":  validate_attendance,
}

CLEAN_FN = {
    "profiles":    clean_student_profiles,
    "performance": clean_student_performance,
    "attendance":  clean_attendance_data,
}


def capture_clean(fn, path):
    buf = io.StringIO()
    old = sys.stdout; sys.stdout = buf
    try:    res = fn(path)
    except: sys.stdout = old; raise
    finally: sys.stdout = old
    return res, buf.getvalue()


def save_raw(uploaded_file) -> Path:
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(uploaded_file.name).stem
    dest = RAW_DIR / f"{stem}_{ts}.csv"
    dest.write_bytes(uploaded_file.getbuffer())
    return dest


def build_comparison(raw_df, cleaned_df):
    shared = [c for c in cleaned_df.columns if c in raw_df.columns]
    r = raw_df[shared].reset_index(drop=True).astype(str)
    c = cleaned_df[shared].reset_index(drop=True).astype(str)
    n = min(len(r), len(c))
    r, c = r.iloc[:n], c.iloc[:n]
    changed = r != c

    def hl(data):
        s = pd.DataFrame("", index=data.index, columns=data.columns)
        for col in data.columns:
            if col in changed.columns:
                s.loc[changed[col], col] = "background-color:#fef08a;color:#713f12;"
        return s

    return c.style.apply(hl, axis=None), changed.any(axis=1).sum(), changed.sum().sum()


def issues_to_csv_bytes(issues: list, filename: str, dataset_type: str) -> bytes:
    buf = io.StringIO()
    w   = csv.writer(buf)
    w.writerow(["file", "dataset_type", "issue"])
    for issue in issues:
        w.writerow([filename, dataset_type, issue])
    return buf.getvalue().encode()


# ═════════════════════════════════════════════════════════════════════════════
# PIPELINE (per file)
# ═════════════════════════════════════════════════════════════════════════════

def run_pipeline(uploaded_file) -> dict:
    res = {
        "filename":     uploaded_file.name,
        "success":      False,
        "dataset_type": None,
        "match_score":  None,
        "fuzzy_notes":  [],          # missing / extra cols from fuzzy match
        "issues":       [],
        "raw_df":       None,
        "cleaned_df":   None,
        "raw_rows":     0,
        "logs":         "",
        "error":        None,
        "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 1 · read
    try:
        raw_df = pd.read_csv(uploaded_file)
        uploaded_file.seek(0)
    except Exception as e:
        res["error"] = f"Could not read CSV: {e}"
        return res

    res["raw_rows"] = len(raw_df)
    res["raw_df"]   = raw_df.copy()

    # normalise for classification
    norm_df = raw_df.copy()
    norm_df.columns = (
        norm_df.columns.str.strip().str.lower().str.replace(" ", "_")
    )

    # 2 · fuzzy classify
    try:
        dtype, score, missing, extra = fuzzy_classify(norm_df)
        res["dataset_type"] = dtype
        res["match_score"]  = score
        if missing:
            res["fuzzy_notes"].append(f"Columns not found (assumed OK): {', '.join(sorted(missing))}")
        if extra:
            res["fuzzy_notes"].append(f"Extra columns ignored: {', '.join(sorted(extra))}")
    except ValueError as e:
        res["error"] = str(e)
        return res

    # 3 · validate
    try:
        res["issues"] = VALIDATE_FN[dtype](norm_df)
    except Exception as e:
        res["issues"] = [f"Validator error: {e}"]

    # 4 · save raw + clean
    try:
        raw_path          = save_raw(uploaded_file)
        cleaned_df, logs  = capture_clean(CLEAN_FN[dtype], raw_path)
        res["cleaned_df"] = cleaned_df
        res["logs"]       = logs
        res["success"]    = True
    except Exception as e:
        res["error"] = f"Cleaning failed: {e}\n\n{traceback.format_exc()}"

    return res


# ═════════════════════════════════════════════════════════════════════════════
# UI
# ═════════════════════════════════════════════════════════════════════════════

# ── sidebar: upload history ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🕑 Upload History")
    if not st.session_state.history:
        st.caption("No runs yet — history appears here after processing.")
    else:
        for entry in reversed(st.session_state.history):
            badge = BADGE_HTML.get(entry["dataset_type"], "")
            status = "✅" if entry["success"] else "❌"
            st.markdown(f"""
            <div class="hist-row">
              <span class="ht">{entry['timestamp']}</span>
              <span class="hf">{status} {entry['filename']}</span>
              <span class="hm">{entry.get('raw_rows',0):,} rows</span>
            </div>""", unsafe_allow_html=True)

        if st.button("Clear history", use_container_width=True):
            st.session_state.history = []
            st.rerun()

# ── header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-bar">
  <h1>🎓 Student Data Review System</h1>
  <p>Upload one or more CSV files — the pipeline will classify, validate, and clean each one automatically.</p>
</div>
""", unsafe_allow_html=True)

# ── multi-file uploader ───────────────────────────────────────────────────────
uploaded_files = st.file_uploader(
    "Drop your CSV files here (you can select multiple)",
    type=["csv"],
    accept_multiple_files=True,
    help="Upload Student Profiles, Performance, and/or Attendance files together.",
)

# detect when the file set changes → clear old results
current_names = {f.name for f in uploaded_files} if uploaded_files else set()
if current_names != st.session_state.last_names:
    st.session_state.results    = []
    st.session_state.last_names = current_names

if not uploaded_files:
    st.info("⬆️  Upload one or more CSV files above to get started.")
    st.markdown("#### Accepted file formats")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""<div class="step-card"><b>👤 Student Profiles</b><br>
        <small>student_id · student_name · class · gender · guardian_contact</small></div>""",
        unsafe_allow_html=True)
    with c2:
        st.markdown("""<div class="step-card"><b>📊 Student Performance</b><br>
        <small>record_id · scores · result · term · subject · teacher_comment …</small></div>""",
        unsafe_allow_html=True)
    with c3:
        st.markdown("""<div class="step-card"><b>📅 Attendance</b><br>
        <small>attendance_id · days_present · days_absent · total_school_days …</small></div>""",
        unsafe_allow_html=True)
    st.stop()

# ── file summary cards ────────────────────────────────────────────────────────
st.markdown(f"**{len(uploaded_files)} file(s) ready**")
for f in uploaded_files:
    st.markdown(f"""
    <div class="file-card">
      <div class="fname">📄 {f.name}</div>
      <div class="fmeta">{f.size / 1024:.1f} KB</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")

# ── run button ────────────────────────────────────────────────────────────────
if st.button("🚀 Run Pipeline", type="primary", use_container_width=True):
    results = []
    progress = st.progress(0, text="Starting…")
    for i, f in enumerate(uploaded_files):
        progress.progress(
            int((i / len(uploaded_files)) * 100),
            text=f"Processing {f.name}…"
        )
        f.seek(0)
        r = run_pipeline(f)
        results.append(r)
        # add to history
        st.session_state.history.append({
            "timestamp":    r["timestamp"],
            "filename":     r["filename"],
            "dataset_type": r["dataset_type"],
            "raw_rows":     r["raw_rows"],
            "success":      r["success"],
        })
    progress.progress(100, text="Done ✅")
    st.session_state.results = results

# ── results ───────────────────────────────────────────────────────────────────
results = st.session_state.results
if not results:
    st.stop()

st.markdown("---")
st.markdown("## Results")

for res in results:
    fname = res["filename"]

    with st.expander(
        f"{'✅' if res['success'] else '❌'}  {fname}",
        expanded=True
    ):
        # ── error state ───────────────────────────────────────────────────────
        if res["error"]:
            st.error(f"Pipeline failed for **{fname}**")
            st.code(res["error"])
            continue

        # ── Step 1: classification ────────────────────────────────────────────
        dtype     = res["dataset_type"]
        badge     = BADGE_HTML.get(dtype, f'<span class="badge badge-unknown">{dtype}</span>')
        score_pct = f"{res['match_score']:.0%}"

        st.markdown(
            f"**Step 1 — Dataset type** &nbsp; {badge} &nbsp;"
            f'<span class="badge badge-ok">Match {score_pct}</span>',
            unsafe_allow_html=True,
        )

        if res["fuzzy_notes"]:
            for note in res["fuzzy_notes"]:
                st.markdown(
                    f'<div class="issue-item issue-warn">🔍 {note}</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("")

        # ── Step 2: validation ────────────────────────────────────────────────
        st.markdown("**Step 2 — Validation report**")
        issues = res["issues"]

        if not issues:
            st.markdown(
                '<div class="issue-item issue-ok">✅ No issues found.</div>',
                unsafe_allow_html=True,
            )
        else:
            for issue in issues:
                st.markdown(
                    f'<div class="issue-item issue-warn">⚠️ {issue}</div>',
                    unsafe_allow_html=True,
                )

        # export validation report
        report_bytes = issues_to_csv_bytes(issues, fname, dtype)
        st.download_button(
            label="⬇️ Download validation report",
            data=report_bytes,
            file_name=f"{Path(fname).stem}_validation_report.csv",
            mime="text/csv",
            key=f"val_{fname}",
        )

        st.markdown("")

        # ── Step 3: before / after ────────────────────────────────────────────
        st.markdown("**Step 3 — Before / After**")

        raw_df     = res["raw_df"]
        cleaned_df = res["cleaned_df"]

        rows_before  = res["raw_rows"]
        rows_after   = len(cleaned_df)
        rows_removed = rows_before - rows_after

        styled_clean, rows_changed, cells_changed = build_comparison(raw_df, cleaned_df)

        m1, m2, m3, m4, m5 = st.columns(5)
        for col_obj, val, label in [
            (m1, f"{rows_before:,}",   "Rows original"),
            (m2, f"{rows_after:,}",    "Rows cleaned"),
            (m3, f"{rows_removed:,}",  "Rows removed"),
            (m4, f"{rows_changed:,}",  "Rows changed"),
            (m5, f"{cells_changed:,}", "Cells changed"),
        ]:
            col_obj.markdown(
                f'<div class="metric-box"><div class="val">{val}</div>'
                f'<div class="lbl">{label}</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("")

        tab_b, tab_a = st.tabs(["📋 Before (raw)", "✅ After (cleaned)"])
        with tab_b:
            st.caption(f"{rows_before:,} rows · {raw_df.shape[1]} columns")
            st.dataframe(raw_df.head(20), use_container_width=True)
        with tab_a:
            st.caption(
                f"{rows_after:,} rows · 🟡 yellow cells were changed by the pipeline"
            )
            st.dataframe(styled_clean, use_container_width=True)

        st.markdown("")

        # ── download cleaned ──────────────────────────────────────────────────
        csv_bytes = cleaned_df.to_csv(index=False).encode()
        ts_label  = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="⬇️ Download Cleaned CSV",
            data=csv_bytes,
            file_name=f"{dtype}_cleaned_{ts_label}.csv",
            mime="text/csv",
            key=f"dl_{fname}",
            use_container_width=True,
        )

        # ── logs ──────────────────────────────────────────────────────────────
        with st.expander("📋 Pipeline logs", expanded=False):
            st.code(
                res["logs"].strip() or "No output captured.",
                language="text",
            )

st.markdown("---")
st.caption("Student Data Review System · Built with Streamlit")
