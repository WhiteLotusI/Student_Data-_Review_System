"""
Dashboard — Student Data Review System
=======================================
Reads cleaned CSVs from data/cleaned/ and renders charts.

Charts:
  - Pass / fail breakdown       (donut)
  - Score averages by class     (bar)
  - Score averages by term      (line)
  - Attendance rates by class   (horizontal bar)
  - Gender distribution         (donut)
  - Top & bottom performers     (bar)
  - Subject-level performance   (bar)
  - Attendance % distribution   (histogram)

Filters (sidebar): class, term, gender
"""

from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard — Student Data Review",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).resolve().parents[1]
CLEAN_DIR = ROOT / "data" / "cleaned"

PERF_FILE = CLEAN_DIR / "cleaned_student_performance_data.csv"
ATT_FILE  = CLEAN_DIR / "attendance_cleaned.csv"
PROF_FILE = CLEAN_DIR / "profiles_cleaned.csv"

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1,h2,h3 { font-family: 'DM Serif Display', serif; }

.header-bar {
    background: linear-gradient(135deg,#0f2027,#203a43,#2c5364);
    padding: 1.75rem 2.5rem; border-radius:16px; margin-bottom:1.5rem; color:white;
}
.header-bar h1 { color:white; margin:0 0 .2rem 0; font-size:1.8rem; }
.header-bar p  { color:#a8c0cc; margin:0; font-size:.95rem; }

.kpi-card {
    background:#1e2d3d; border:1px solid #2c4a5e;
    border-radius:12px; padding:1.1rem 1rem; text-align:center;
}
.kpi-card .val { font-size:2rem; font-weight:700; color:#7dd3f0; }
.kpi-card .lbl { font-size:.78rem; color:#94a3b8; margin-top:.25rem; }
.kpi-card .sub { font-size:.72rem; color:#64748b; margin-top:.1rem; }

.section-title {
    font-family:'DM Serif Display',serif;
    font-size:1.15rem; color:#e2e8f0;
    border-bottom:1px solid #2c4a5e;
    padding-bottom:.4rem; margin:1.5rem 0 1rem 0;
}

.no-data {
    background:#1a2535; border:1px dashed #2c4a5e;
    border-radius:10px; padding:2rem; text-align:center;
    color:#64748b; font-size:.9rem;
}
</style>
""", unsafe_allow_html=True)

# ── plotly theme ──────────────────────────────────────────────────────────────
COLORS   = ["#38bdf8","#34d399","#fb923c","#a78bfa","#f472b6","#facc15","#4ade80"]
PASS_COL = {"Pass": "#34d399", "Fail": "#f87171"}
BG       = "rgba(0,0,0,0)"
FONT_COL = "#cbd5e1"

def base_layout(fig, height=340):
    fig.update_layout(
        height=height,
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font_color=FONT_COL,
        margin=dict(l=16, r=16, t=36, b=16),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font_color=FONT_COL,
        ),
    )
    fig.update_xaxes(gridcolor="#1e2d3d", zerolinecolor="#1e2d3d")
    fig.update_yaxes(gridcolor="#1e2d3d", zerolinecolor="#1e2d3d")
    return fig


# ── load data ─────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_csv(path: Path):
    if path.exists():
        return pd.read_csv(path)
    return None

def reload_all():
    load_csv.clear()

perf_raw = load_csv(PERF_FILE)
att_raw  = load_csv(ATT_FILE)
prof_raw = load_csv(PROF_FILE)

has_perf = perf_raw is not None
has_att  = att_raw  is not None
has_prof = prof_raw is not None

# ── header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-bar">
  <h1>📊 Student Dashboard</h1>
  <p>Insights from cleaned data — run the pipeline first to populate charts.</p>
</div>
""", unsafe_allow_html=True)

if not any([has_perf, has_att, has_prof]):
    st.markdown("""
    <div class="no-data">
      No cleaned data found yet.<br>
      Go to the <b>Pipeline</b> page, upload your CSV files, and run the pipeline first.
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔽 Filters")

    if st.button("🔄 Refresh data", use_container_width=True):
        reload_all()
        st.rerun()

    # class filter
    all_classes = set()
    if has_perf and "class" in perf_raw.columns:
        all_classes |= set(perf_raw["class"].dropna().unique())
    if has_att and "class" in att_raw.columns:
        all_classes |= set(att_raw["class"].dropna().unique())
    if has_prof and "class" in prof_raw.columns:
        all_classes |= set(prof_raw["class"].dropna().unique())

    all_classes = sorted(all_classes)
    sel_classes = st.multiselect("Class", all_classes, default=all_classes)

    # term filter
    all_terms = set()
    if has_perf and "term" in perf_raw.columns:
        all_terms |= set(perf_raw["term"].dropna().unique())
    if has_att and "term" in att_raw.columns:
        all_terms |= set(att_raw["term"].dropna().unique())

    all_terms = sorted(all_terms)
    sel_terms = st.multiselect("Term", all_terms, default=all_terms)

    # gender filter
    all_genders = set()
    if has_perf and "gender" in perf_raw.columns:
        all_genders |= set(perf_raw["gender"].dropna().unique())
    if has_prof and "gender" in prof_raw.columns:
        all_genders |= set(prof_raw["gender"].dropna().unique())

    all_genders = sorted(all_genders)
    sel_genders = st.multiselect("Gender", all_genders, default=all_genders)

    st.markdown("---")
    st.caption("Filters apply to all charts below.")


# ── apply filters ─────────────────────────────────────────────────────────────
def apply_filters(df):
    if df is None:
        return None
    d = df.copy()
    if "class" in d.columns and sel_classes:
        d = d[d["class"].isin(sel_classes)]
    if "term" in d.columns and sel_terms:
        d = d[d["term"].isin(sel_terms)]
    if "gender" in d.columns and sel_genders:
        d = d[d["gender"].isin(sel_genders)]
    return d

perf = apply_filters(perf_raw)
att  = apply_filters(att_raw)
prof = apply_filters(prof_raw)


# ═════════════════════════════════════════════════════════════════════════════
# KPI ROW
# ═════════════════════════════════════════════════════════════════════════════

st.markdown('<div class="section-title">Overview</div>', unsafe_allow_html=True)

kpi_cols = st.columns(5)

# total students
total_students = 0
if has_prof and prof is not None and "student_id" in prof.columns:
    total_students = prof["student_id"].nunique()
elif has_perf and perf is not None and "student_id" in perf.columns:
    total_students = perf["student_id"].nunique()

# pass rate
pass_rate = None
if has_perf and perf is not None and "result" in perf.columns and len(perf):
    pass_rate = (perf["result"].str.strip().str.title() == "Pass").mean() * 100

# avg total score
avg_score = None
if has_perf and perf is not None and "total_score" in perf.columns and len(perf):
    avg_score = perf["total_score"].mean()

# avg attendance
avg_att = None
if has_att and att is not None and "attendance_percent" in att.columns and len(att):
    avg_att = att["attendance_percent"].mean()

# gender split
gender_split = "—"
if has_prof and prof is not None and "gender" in prof.columns and len(prof):
    gc = prof["gender"].value_counts()
    if "Male" in gc and "Female" in gc:
        gender_split = f"{gc.get('Male',0)}M / {gc.get('Female',0)}F"

for col, val, label, sub in [
    (kpi_cols[0], f"{total_students:,}"             if total_students else "—", "Total Students",    "unique IDs"),
    (kpi_cols[1], f"{pass_rate:.1f}%"               if pass_rate is not None else "—", "Pass Rate", "of all records"),
    (kpi_cols[2], f"{avg_score:.1f}"                if avg_score is not None else "—", "Avg Score", "out of 100"),
    (kpi_cols[3], f"{avg_att:.1f}%"                 if avg_att  is not None else "—", "Avg Attendance", "across classes"),
    (kpi_cols[4], gender_split,                                                         "Gender Split", "Male / Female"),
]:
    col.markdown(
        f'<div class="kpi-card"><div class="val">{val}</div>'
        f'<div class="lbl">{label}</div><div class="sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════════════════════════════════════
# PERFORMANCE SECTION
# ═════════════════════════════════════════════════════════════════════════════

if has_perf and perf is not None and len(perf):

    st.markdown('<div class="section-title">Performance</div>', unsafe_allow_html=True)

    row1_c1, row1_c2, row1_c3 = st.columns([1, 2, 2])

    # ── donut: pass / fail ────────────────────────────────────────────────────
    with row1_c1:
        st.markdown("##### Pass / Fail breakdown")
        if "result" in perf.columns:
            pf = (
                perf["result"]
                .str.strip().str.title()
                .value_counts()
                .reset_index()
            )
            pf.columns = ["Result", "Count"]
            fig = px.pie(
                pf, names="Result", values="Count",
                hole=0.55,
                color="Result",
                color_discrete_map=PASS_COL,
            )
            fig.update_traces(textposition="outside", textinfo="percent+label")
            st.plotly_chart(base_layout(fig, 300), use_container_width=True)
        else:
            st.info("No `result` column found.")

    # ── bar: avg score by class ───────────────────────────────────────────────
    with row1_c2:
        st.markdown("##### Avg total score by class")
        if "class" in perf.columns and "total_score" in perf.columns:
            by_class = (
                perf.groupby("class")["total_score"]
                .mean().round(1).reset_index()
                .sort_values("class")
            )
            fig = px.bar(
                by_class, x="class", y="total_score",
                color="class", color_discrete_sequence=COLORS,
                labels={"class": "Class", "total_score": "Avg Score"},
                text="total_score",
            )
            fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
            fig.update_layout(showlegend=False)
            st.plotly_chart(base_layout(fig), use_container_width=True)
        else:
            st.info("Need `class` and `total_score` columns.")

    # ── line: avg score by term ───────────────────────────────────────────────
    with row1_c3:
        st.markdown("##### Avg score by term")
        if "term" in perf.columns and "total_score" in perf.columns:
            by_term = (
                perf.groupby("term")["total_score"]
                .mean().round(1).reset_index()
                .sort_values("term")
            )
            fig = px.line(
                by_term, x="term", y="total_score",
                markers=True,
                labels={"term": "Term", "total_score": "Avg Score"},
                color_discrete_sequence=["#38bdf8"],
            )
            fig.update_traces(line_width=2.5, marker_size=8)
            st.plotly_chart(base_layout(fig), use_container_width=True)
        else:
            st.info("Need `term` and `total_score` columns.")

    row2_c1, row2_c2 = st.columns(2)

    # ── bar: subject-level avg score ──────────────────────────────────────────
    with row2_c1:
        st.markdown("##### Avg score by subject")
        if "subject" in perf.columns and "total_score" in perf.columns:
            by_sub = (
                perf.groupby("subject")["total_score"]
                .mean().round(1).reset_index()
                .sort_values("total_score", ascending=True)
            )
            fig = px.bar(
                by_sub, x="total_score", y="subject",
                orientation="h",
                color="total_score",
                color_continuous_scale=["#1e3a5f", "#38bdf8"],
                labels={"subject": "Subject", "total_score": "Avg Score"},
                text="total_score",
            )
            fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(base_layout(fig, 380), use_container_width=True)
        else:
            st.info("Need `subject` and `total_score` columns.")

    # ── bar: top & bottom 10 students ─────────────────────────────────────────
    with row2_c2:
        st.markdown("##### Top & bottom 10 students")
        if "student_name" in perf.columns and "total_score" in perf.columns:
            avg_by_student = (
                perf.groupby("student_name")["total_score"]
                .mean().round(1).reset_index()
                .sort_values("total_score", ascending=False)
            )
            top10    = avg_by_student.head(10).copy()
            bottom10 = avg_by_student.tail(10).copy()
            top10["group"]    = "Top 10"
            bottom10["group"] = "Bottom 10"
            combined = pd.concat([top10, bottom10]).sort_values("total_score", ascending=True)

            fig = px.bar(
                combined, x="total_score", y="student_name",
                orientation="h",
                color="group",
                color_discrete_map={"Top 10": "#34d399", "Bottom 10": "#f87171"},
                labels={"student_name": "", "total_score": "Avg Score", "group": ""},
                text="total_score",
            )
            fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
            st.plotly_chart(base_layout(fig, 380), use_container_width=True)
        else:
            st.info("Need `student_name` and `total_score` columns.")

    # ── pass/fail by class ────────────────────────────────────────────────────
    if "class" in perf.columns and "result" in perf.columns:
        st.markdown("##### Pass / Fail count by class")
        pf_class = (
            perf.assign(result=perf["result"].str.strip().str.title())
            .groupby(["class", "result"])
            .size().reset_index(name="count")
        )
        fig = px.bar(
            pf_class, x="class", y="count", color="result",
            barmode="group",
            color_discrete_map=PASS_COL,
            labels={"class": "Class", "count": "Students", "result": "Result"},
        )
        st.plotly_chart(base_layout(fig, 300), use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# ATTENDANCE SECTION
# ═════════════════════════════════════════════════════════════════════════════

if has_att and att is not None and len(att):

    st.markdown('<div class="section-title">Attendance</div>', unsafe_allow_html=True)

    att_c1, att_c2 = st.columns(2)

    # ── horizontal bar: avg attendance by class ───────────────────────────────
    with att_c1:
        st.markdown("##### Avg attendance % by class")
        if "class" in att.columns and "attendance_percent" in att.columns:
            by_class = (
                att.groupby("class")["attendance_percent"]
                .mean().round(1).reset_index()
                .sort_values("attendance_percent", ascending=True)
            )
            fig = px.bar(
                by_class, x="attendance_percent", y="class",
                orientation="h",
                color="attendance_percent",
                color_continuous_scale=["#f87171", "#facc15", "#34d399"],
                range_color=[50, 100],
                labels={"class": "Class", "attendance_percent": "Avg Attendance %"},
                text="attendance_percent",
            )
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(base_layout(fig, 300), use_container_width=True)
        else:
            st.info("Need `class` and `attendance_percent` columns.")

    # ── histogram: attendance distribution ────────────────────────────────────
    with att_c2:
        st.markdown("##### Attendance % distribution")
        if "attendance_percent" in att.columns:
            fig = px.histogram(
                att, x="attendance_percent",
                nbins=20,
                color_discrete_sequence=["#38bdf8"],
                labels={"attendance_percent": "Attendance %", "count": "Students"},
            )
            fig.update_traces(marker_line_width=0.5, marker_line_color="#0f2027")
            # reference line at 75%
            fig.add_vline(
                x=75, line_dash="dash", line_color="#facc15",
                annotation_text="75% threshold",
                annotation_font_color="#facc15",
            )
            st.plotly_chart(base_layout(fig, 300), use_container_width=True)
        else:
            st.info("Need `attendance_percent` column.")

    # ── line: avg attendance by term ──────────────────────────────────────────
    if "term" in att.columns and "attendance_percent" in att.columns:
        st.markdown("##### Avg attendance by term")
        by_term = (
            att.groupby("term")["attendance_percent"]
            .mean().round(1).reset_index()
            .sort_values("term")
        )
        fig = px.line(
            by_term, x="term", y="attendance_percent",
            markers=True,
            color_discrete_sequence=["#34d399"],
            labels={"term": "Term", "attendance_percent": "Avg Attendance %"},
        )
        fig.update_traces(line_width=2.5, marker_size=8)
        fig.add_hline(
            y=75, line_dash="dash", line_color="#facc15",
            annotation_text="75% threshold",
            annotation_font_color="#facc15",
        )
        st.plotly_chart(base_layout(fig, 280), use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# PROFILES SECTION
# ═════════════════════════════════════════════════════════════════════════════

if has_prof and prof is not None and len(prof):

    st.markdown('<div class="section-title">Student Profiles</div>', unsafe_allow_html=True)

    prof_c1, prof_c2 = st.columns(2)

    # ── donut: gender distribution ────────────────────────────────────────────
    with prof_c1:
        st.markdown("##### Gender distribution")
        if "gender" in prof.columns:
            gd = prof["gender"].value_counts().reset_index()
            gd.columns = ["Gender", "Count"]
            fig = px.pie(
                gd, names="Gender", values="Count",
                hole=0.55,
                color="Gender",
                color_discrete_map={"Male": "#38bdf8", "Female": "#f472b6"},
            )
            fig.update_traces(textposition="outside", textinfo="percent+label")
            st.plotly_chart(base_layout(fig, 300), use_container_width=True)
        else:
            st.info("No `gender` column found.")

    # ── bar: students per class ───────────────────────────────────────────────
    with prof_c2:
        st.markdown("##### Students per class")
        if "class" in prof.columns:
            by_class = (
                prof["class"].value_counts().reset_index()
            )
            by_class.columns = ["Class", "Count"]
            by_class = by_class.sort_values("Class")
            fig = px.bar(
                by_class, x="Class", y="Count",
                color="Class",
                color_discrete_sequence=COLORS,
                labels={"Class": "Class", "Count": "Students"},
                text="Count",
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(showlegend=False)
            st.plotly_chart(base_layout(fig, 300), use_container_width=True)
        else:
            st.info("No `class` column found.")

    # ── gender split by class ─────────────────────────────────────────────────
    if "class" in prof.columns and "gender" in prof.columns:
        st.markdown("##### Gender split by class")
        gc = (
            prof.groupby(["class", "gender"])
            .size().reset_index(name="count")
        )
        fig = px.bar(
            gc, x="class", y="count", color="gender",
            barmode="group",
            color_discrete_map={"Male": "#38bdf8", "Female": "#f472b6"},
            labels={"class": "Class", "count": "Students", "gender": "Gender"},
        )
        st.plotly_chart(base_layout(fig, 280), use_container_width=True)


st.markdown("---")
st.caption("Student Data Review System · Dashboard · Built with Streamlit")
