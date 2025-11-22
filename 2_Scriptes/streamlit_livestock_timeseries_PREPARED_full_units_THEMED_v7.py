
from __future__ import annotations
import streamlit as st, pandas as pd, altair as alt
from pathlib import Path

# Try to import plotly; if missing, we will show a helpful message in the Map tab.
try:
    import plotly.express as px
    HAS_PLOTLY = True
    # Green (low) -> Teal/Blue -> Yellow -> Orange -> Red (high)
    CORP_SCALE = [
        [0.00, "#ABDDA4"],
        [0.11, "#66C2A5"],
        [0.22, "#3288BD"],
        [0.33, "#5E4FA2"],
        [0.44, "#FEE08B"],
        [0.56, "#FDAE61"],
        [0.67, "#F46D43"],
        [0.78, "#D53E4F"],
        [1.00, "#9E0142"]
    ]
except Exception:
    HAS_PLOTLY = False

st.set_page_config(page_title="European Livestock Trends", layout="wide")
st.title("European Livestock Emissions")

DEFAULT_PREPARED = "1_Donnees/livestock_PREPARED_long.csv"
REGION_LABELS = ["Europe (group total)", "EU (group total)", "EU/EEA+UK (group total)"]
REGION_SET = set(REGION_LABELS)

EUROPE_WIDE = {"Albania","Andorra","Armenia","Austria","Azerbaijan","Belarus","Belgium","Bosnia and Herzegovina","Bulgaria",
               "Croatia","Cyprus","Czechia","Czech Republic","Denmark","Estonia","Finland","France","Georgia","Germany","Greece",
               "Hungary","Iceland","Ireland","Italy","Kazakhstan","Kosovo","Latvia","Liechtenstein","Lithuania","Luxembourg",
               "Malta","Moldova","Monaco","Montenegro","Netherlands","North Macedonia","Norway","Poland","Portugal","Romania",
               "Russia","San Marino","Serbia","Slovakia","Slovenia","Spain","Sweden","Switzerland","Turkey","Ukraine",
               "United Kingdom","UK","Vatican City"}


# ---------- Corporate palette & theming ----------
CORP = {
    "bg":      "#f5f0e6",  # warm beige background
    "panel":   "#e7dfcf",  # lighter beige panels / sidebar
    "text":    "#2e2b26",  # deep brown text
    "accent":  "#6b8e23",  # olive drab (khaki green)
    "accent2": "#8f9779",  # sage green
    "brown":   "#8b6b4a",  # mid brown
}

# 1) Streamlit CSS (backgrounds, sidebar, buttons, tabs)
st.markdown(f'''
<style>
/* App background */
.stApp {{
  background-color: {CORP["bg"]};
  color: {CORP["text"]};
}}

/* Sidebar background */
section[data-testid="stSidebar"] > div:first-child {{
  background-color: {CORP["panel"]} !important;
}}

/* Buttons & downloads */
.stButton button, .stDownloadButton button {{
  background-color: {CORP["accent"]} !important;
  color: white !important;
  border: 0 !important;
  border-radius: 10px !important;
}}
.stButton button:hover, .stDownloadButton button:hover {{
  filter: brightness(0.95);
}}

/* Tabs */
.stTabs [role="tablist"] button[role="tab"] {{
  color: {CORP["text"]};
}}
.stTabs [role="tablist"] button[aria-selected="true"] {{
  border-bottom: 3px solid {CORP["accent"]};
}}

/* Cards/panels */
.block-container {{
  background: transparent;
}}

/* Inputs labels */
label, .stSelectbox label, .stRadio label {{
  color: {CORP["text"]} !important;
}}
</style>
''', unsafe_allow_html=True)

# 2) Altair theme
import altair as alt
ALT_CATEGORY = ["#9E0142","#D53E4F","#F46D43","#FDAE61","#FEE08B","#E6F598","#ABDDA4","#66C2A5","#3288BD","#5E4FA2","#9E0142","#D53E4F","#F46D43","#FDAE61","#FEE08B","#E6F598","#ABDDA4","#66C2A5","#3288BD","#5E4FA2","#9E0142","#D53E4F","#F46D43","#FDAE61","#FEE08B","#E6F598","#ABDDA4","#66C2A5","#3288BD","#5E4FA2","#9E0142","#D53E4F","#F46D43","#FDAE61","#FEE08B","#E6F598","#ABDDA4","#66C2A5","#3288BD","#5E4FA2"]
def _corp_altair_theme():
    return {
        "config": {
            "range": {"category": ALT_CATEGORY},
            "view": {"stroke": "transparent"},
            "axis": {"labelColor": CORP["text"], "titleColor": CORP["text"]},
            "legend": {"labelColor": CORP["text"], "titleColor": CORP["text"]},
            "title": {"color": CORP["text"]}, "mark": {"strokeWidth": 2} ,
        }
    }
alt.themes.register("corp", _corp_altair_theme)
alt.themes.enable("corp")

# --- Reduced palette for pie charts: 7 evenly spaced colors from the user palette ---
USER_PLOT_PALETTE = ["#9E0142","#D53E4F","#F46D43","#FDAE61","#FEE08B","#E6F598","#ABDDA4","#66C2A5","#3288BD","#5E4FA2"]
PIE_COLORS_COUNT = 7
PIE_IDX = [round(i*(len(USER_PLOT_PALETTE)-1)/(PIE_COLORS_COUNT-1)) for i in range(PIE_COLORS_COUNT)]
PIE_PALETTE = [USER_PLOT_PALETTE[i] for i in PIE_IDX]


# Reduced palette for pie charts (fewer colors, still spanning endpoints)
PIE_PALETTE = ["#9E0142","#F46D43","#FEE08B","#ABDDA4","#3288BD","#5E4FA2"]

# 3) Plotly theme utilities
try:
    import plotly.express as px
    HAS_PLOTLY = True
    # Green (low) -> Teal/Blue -> Yellow -> Orange -> Red (high)
    CORP_SCALE = [
        [0.00, "#ABDDA4"],
        [0.11, "#66C2A5"],
        [0.22, "#3288BD"],
        [0.33, "#5B44C3"],
        [0.44, "#FEE08B"],
        [0.56, "#FDAE61"],
        [0.67, "#F46D43"],
        [0.78, "#D53E4F"],
        [1.00, "#9E0142"]
    ]
except Exception:
    HAS_PLOTLY = False


def metric_unit_label(metric: str) -> str:
    # Map metric to a human label with units (emissions shown in kilotonnes of CO₂e)
    if metric == "Total_CO2e": return "Total (kt CO₂e)"
    if metric == "CH4_CO2e":   return "CH₄ (kt CO₂e)"
    if metric == "N2O_CO2e":   return "N₂O (kt CO₂e)"
    if metric == "LSU":        return "Livestock Units (LSU)"
    if metric == "Stocks":     return "Headcount (head)"
    return metric

@st.cache_data
def load_prepared(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    need = {"Area","Item","Year","Metric","Value","item_kind","is_all_animals","is_atomic"}
    miss = need.difference(df.columns)
    if miss:
        st.error(f"Prepared CSV missing columns: {', '.join(sorted(miss))}"); st.stop()
    df["item_kind"] = df["item_kind"].astype(str)
    return df

path = Path(DEFAULT_PREPARED)
if not path.exists():
    st.warning(f"Prepared CSV not found at:\n{path}\nUpload below or update DEFAULT_PREPARED.")
    uploaded = st.file_uploader("Upload the prepared CSV", type=["csv"])
    if uploaded is None: st.stop()
    df = pd.read_csv(uploaded)
else:
    df = load_prepared(path)

year_min, year_max = int(df["Year"].min()), int(df["Year"].max())
DEFAULT_START = max(1990, year_min)
DEFAULT_END   = min(2022, year_max)

# --- Tabs ---
tab_ts, tab_pie, tab_map = st.tabs(["Time trends", "Composition", "Map"])

# =========================
# Time Series TAB
# =========================
with tab_ts:
    with st.sidebar:
        st.header("Metric & period")
        metric = st.selectbox("Metric", sorted(df["Metric"].unique().tolist()),
                              index=sorted(df["Metric"].unique().tolist()).index("Total_CO2e") if "Total_CO2e" in df["Metric"].unique() else 0)
        year_range = st.slider("Year range", min_value=year_min, max_value=year_max,
                               value=(DEFAULT_START, DEFAULT_END), step=1)

    with st.sidebar:
        st.header("Item group")
        group = st.radio("Choose one group", ["All animals","Aggregate","Atomic"], index=0, horizontal=False)
    group_key = {"All animals":"all_animals", "Aggregate":"aggregate", "Atomic":"atomic"}[group]

    subset = df[(df["Metric"]==metric) & (df["item_kind"]==group_key)]
    items_all = sorted(subset["Item"].dropna().unique().tolist())

    ITEMS_KEY = "items_prepared_multiselect_by_group"
    if ITEMS_KEY not in st.session_state:
        st.session_state[ITEMS_KEY] = list(items_all[:1]) if group_key=="all_animals" else list(items_all)

    if "last_group_key" not in st.session_state or st.session_state["last_group_key"] != group_key:
        st.session_state[ITEMS_KEY] = list(items_all[:1]) if group_key=="all_animals" else list(items_all)
    st.session_state["last_group_key"] = group_key

    valid_defaults = [d for d in st.session_state[ITEMS_KEY] if d in items_all]
    if not valid_defaults:
        valid_defaults = list(items_all[:1]) if group_key=="all_animals" else list(items_all)
    st.session_state[ITEMS_KEY] = valid_defaults

    st.write(f"**Items — {group}**")
    c1,c2,c3 = st.columns(3)
    with c1:
        if st.button("Select all"):
            st.session_state[ITEMS_KEY] = list(items_all[:1]) if group_key=="all_animals" else list(items_all)
    with c2:
        if st.button("Clear"):
            st.session_state[ITEMS_KEY] = []
    with c3:
        if group_key=="all_animals":
            st.caption("All animals is exclusive by design")

    items = st.multiselect("", options=items_all, default=st.session_state[ITEMS_KEY], key=ITEMS_KEY, max_selections=None if group_key!="all_animals" else 1)
    if not items:
        st.info("Select at least one item."); st.stop()

    with st.sidebar:
        st.header("View mode")
        show_region = st.checkbox("Show regional total instead of countries", value=False)
        region_choice = st.selectbox("Region total", REGION_LABELS, index=0, disabled=not show_region)

    base = df[(df["Metric"]==metric) & (df["Year"]>=year_range[0]) & (df["Year"]<=year_range[1]) & (df["item_kind"]==group_key)]
    base = base[base["Item"].isin(items)]
    if base.empty: st.info("No data for current filters."); st.stop()

    if show_region:
        sub = base[base["Area"] == region_choice].copy()
        if sub.empty:
            st.info(f"No region total rows found for: {region_choice}. Did you run the latest preprocessor?"); st.stop()
        totals = sub.groupby(["Area","Year"], as_index=False)["Value"].sum().rename(columns={"Value":"SeriesValue"})
    else:
        EU = {"Austria","Belgium","Bulgaria","Croatia","Cyprus","Czechia","Czech Republic","Denmark","Estonia",
              "Finland","France","Germany","Greece","Hungary","Ireland","Italy","Latvia","Lithuania","Luxembourg",
              "Malta","Netherlands","Poland","Portugal","Romania","Slovakia","Slovenia","Spain","Sweden"}
        EEA_PLUS_UK = EU.union({"Iceland","Liechtenstein","Norway","United Kingdom","UK"})
        EUROPE_WIDE = {"Albania","Andorra","Armenia","Austria","Azerbaijan","Belarus","Belgium","Bosnia and Herzegovina","Bulgaria",
                       "Croatia","Cyprus","Czechia","Czech Republic","Denmark","Estonia","Finland","France","Georgia","Germany","Greece",
                       "Hungary","Iceland","Ireland","Italy","Kazakhstan","Kosovo","Latvia","Liechtenstein","Lithuania","Luxembourg",
                       "Malta","Moldova","Monaco","Montenegro","Netherlands","North Macedonia","Norway","Poland","Portugal","Romania",
                       "Russia","San Marino","Serbia","Slovakia","Slovenia","Spain","Sweden","Switzerland","Turkey","Ukraine",
                       "United Kingdom","UK","Vatican City"}
        def intersect_available(names_set: set[str], available: set[str]) -> list[str]:
            return sorted(list(available.intersection(names_set)))
        with st.sidebar:
            st.header("Countries")
            mode = st.radio("Country selection mode", ["Preset (Top 10)", "Custom (pick countries)"], horizontal=False)
            add_ch = False
            preset_choice = None
            available_countries = sorted(df["Area"].dropna().unique().tolist())
            if mode == "Preset (Top 10)":
                preset_choice = st.selectbox("Preset group", ["Europe", "EU", "EU/EEA + UK"], index=0)
                add_ch = st.checkbox("Add Switzerland 🇨🇭", value=False)
            else:
                selected_countries = st.multiselect("Countries (max 12)", options=available_countries, max_selections=12)

        sub = base.copy()
        available_countries = set(sub["Area"].dropna().unique().tolist())
        def inter(names): return sorted(list(available_countries.intersection(names)))
        if mode == "Preset (Top 10)":
            if preset_choice == "Europe": pool = inter(EUROPE_WIDE)
            elif preset_choice == "EU":   pool = inter(EU)
            else:                         pool = inter(EEA_PLUS_UK)
            latest_year = sub["Year"].max()
            latest = sub[(sub["Year"]==latest_year) & (sub["Area"].isin(pool))]
            ranked = latest.groupby("Area", as_index=False)["Value"].sum().sort_values("Value", ascending=False)["Area"].tolist()
            keep = ranked[:10]
            if add_ch and "Switzerland" in available_countries and "Switzerland" not in keep:
                keep.append("Switzerland")
        else:
            keep = selected_countries if 'selected_countries' in locals() and selected_countries else []

        if keep: sub = sub[sub["Area"].isin(keep)]
        if sub.empty: st.info("No data after country selection."); st.stop()
        totals = sub.groupby(["Area","Year"], as_index=False)["Value"].sum().rename(columns={"Value":"SeriesValue"})

    labels = {"Stocks":"Headcount (stocks)","CH4_CO2e":"CH₄ (kt CO₂e)","N2O_CO2e":"N₂O (kt CO₂e)","Total_CO2e":"Total (kt CO₂e)","LSU":"Livestock Units (LSU)"}
    y_label = labels.get(metric, metric)

    subtitle = f"{metric_unit_label(metric)} — {year_range[0]}–{year_range[1]}"
    if show_region:
        subtitle += f" — {region_choice}"
    st.subheader(subtitle)
    st.caption(f"Group: {group}")

    order_latest = (totals[totals["Year"]==totals["Year"].max()].sort_values("SeriesValue", ascending=False)["Area"].tolist())

    chart = (alt.Chart(totals).mark_line(point=True).encode(
        x=alt.X("Year:O", title="Year"),
        y=alt.Y("SeriesValue:Q", title=y_label),
        color=alt.Color("Area:N", sort=order_latest, legend=alt.Legend(title="Country" if not show_region else "Region")),
        tooltip=[alt.Tooltip("Area:N", title="Country" if not show_region else "Region"),
                 alt.Tooltip("Year:O", title="Year"),
                 alt.Tooltip("SeriesValue:Q", title=y_label, format=",.0f")]
    ).properties(height=520))
    st.altair_chart(chart, use_container_width=True)

    csv_bytes = totals.to_csv(index=False).encode("utf-8")
    fname = f"timeseries_{metric}_{group_key}_{year_range[0]}_{year_range[1]}"
    fname += "_REGION.csv" if show_region else ".csv"
    st.download_button("Download series as CSV", data=csv_bytes, file_name=fname, mime="text/csv")

# =========================
# Pie TAB
# =========================
with tab_pie:
    st.subheader("Shares by aggregate animal group (pie)")
    st.caption("Pick a country/region and a single year; choose which emissions metric to break down (default: Total_CO2e).")

    metric_pie = st.selectbox("Pie metric", ["Total_CO2e","CH4_CO2e","N2O_CO2e"], index=0)
    year_pie = st.slider("Pie year", min_value=year_min, max_value=year_max, value=min(2022, year_max), step=1)

    agg = df[(df["item_kind"]=="aggregate") & (df["Metric"]==metric_pie) & (df["Year"]==year_pie)].copy()
    if agg.empty:
        st.info("No aggregate rows found for that year/metric."); st.stop()

    areas = sorted(agg["Area"].unique().tolist())
    regions_first = [x for x in REGION_LABELS if x in areas]
    countries = [a for a in areas if a not in regions_first]
    area_choice = st.selectbox("Choose country/region", regions_first + countries, index=0 if regions_first else 0)

    pie_df = agg[agg["Area"]==area_choice][["Item","Value"]].groupby("Item", as_index=False)["Value"].sum()
    total_val = float(pie_df["Value"].sum()) if not pie_df.empty else 0.0

    if total_val <= 0 or pie_df.empty:
        st.info("No positive values to plot for this selection."); st.stop()

    pie_df["Share"] = pie_df["Value"] / total_val
    pie_df["Share (%)"] = (pie_df["Share"] * 100).round(1)
    pie_df_display = pie_df[["Item","Value","Share (%)"]].sort_values("Value", ascending=False)
    # Rename Value column with units for display
    pie_df_display = pie_df_display.rename(columns={"Value": f"Value ({'kt CO₂e' if metric_pie in ['Total_CO2e', 'CH4_CO2e', 'N2O_CO2e'] else metric_pie})"})

    pie = alt.Chart(pie_df).mark_arc(outerRadius=160).encode(
        theta=alt.Theta(field="Value", type="quantitative", stack=True),
        color=alt.Color(field="Item", type="nominal", scale=alt.Scale(range=PIE_PALETTE), legend=alt.Legend(title="Aggregate group")),
        tooltip=[alt.Tooltip("Item:N", title="Group"),
                 alt.Tooltip("Value:Q", title=("Value (kt CO₂e)" if metric_pie in ["Total_CO2e","CH4_CO2e","N2O_CO2e"] else "Value"), format=",.0f"),
                 alt.Tooltip("Share:Q", title="Share", format=".1%")]
    ).properties(width=520, height=520, title=f"{metric_unit_label(metric_pie)} — {area_choice} — {year_pie}")

    st.altair_chart(pie, use_container_width=False)

    st.write("Data behind the pie:")
    st.dataframe(pie_df_display, use_container_width=True)
    st.download_button("Download pie data as CSV",
                       data=pie_df_display.to_csv(index=False).encode("utf-8"),
                       file_name=f"pie_{metric_pie}_{area_choice.replace(' ','_')}_{year_pie}.csv",
                       mime="text/csv")

# =========================
# Map TAB
# =========================
with tab_map:
    st.subheader("Map of totals — Europe (All animals only)")

    metric_map = st.radio("Map metric", ["Total_CO2e","LSU"], index=0, horizontal=True)
    year_map = st.slider("Map year", min_value=year_min, max_value=year_max, value=min(2022, year_max), step=1)

    if not HAS_PLOTLY:
        st.error("Plotly is not installed. In a terminal, run:\n\n  py -m pip install plotly\n\nThen rerun the app.")
        st.stop()

    sub = df[(df["item_kind"]=="all_animals") & (df["Metric"]==metric_map) & (df["Year"]==year_map)].copy()
    sub = sub[~sub["Area"].isin(REGION_SET)].copy()

    available = set(sub["Area"].unique().tolist())
    europe_names = sorted(list(available.intersection(EUROPE_WIDE)))
    if not europe_names:
        st.info("No European country rows found for this selection."); st.stop()
    sub = sub[sub["Area"].isin(europe_names)]

    map_df = sub.groupby(["Area"], as_index=False)["Value"].sum()

    name_fix = {
        "UK": "United Kingdom",
        "Russia": "Russian Federation",
    }
    map_df["Area"] = map_df["Area"].replace(name_fix)

    label = "Total (kt CO₂e)" if metric_map=="Total_CO2e" else "Livestock Units (LSU)"
    fig = px.choropleth(
        map_df,
        locations="Area",
        locationmode="country names",
        color="Value",
        scope="europe",
        color_continuous_scale=CORP_SCALE,
        labels={"Value": label, "Area": "Country"},
        title=f"{label} — Europe — {year_map}",
    )
    fig.update_layout(margin=dict(l=10,r=10,t=50,b=10), paper_bgcolor=CORP["bg"], plot_bgcolor=CORP["panel"], font_color=CORP["text"])

    st.plotly_chart(fig, use_container_width=True)

    st.write("Mapped values:")
    map_df_display = map_df.rename(columns={"Value": ("Value (kt CO₂e)" if metric_map=="Total_CO2e" else "Value (LSU)")})
    st.dataframe(map_df_display.sort_values(map_df_display.columns[1], ascending=False), use_container_width=True)
    st.download_button(
        "Download map data as CSV",
        data=map_df_display.to_csv(index=False).encode("utf-8"),
        file_name=f"map_{metric_map}_{year_map}.csv",
        mime="text/csv"
    )
