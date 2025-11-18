import streamlit as st
import pandas as pd
import requests
import os
from datetime import date

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Timeline", page_icon="📈")

st.markdown("# Emissions Timeline")

scope = st.radio("Show timeline for:", ["All People", "By Major"], index=0)

# Common controls
col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    start_date = st.date_input("Start date", value=None)
with col2:
    end_date = st.date_input("End date", value=None)
with col3:
    interval = st.selectbox("Interval", ["month", "week", "day", "year"], index=2)

students_only = False
major_name = None

if scope == "By Major":
    # Fetch list of majors
    try:
        r = requests.get(f"{API_BASE_URL}/timeline/majors/list", timeout=6)
        r.raise_for_status()
        majors_resp = r.json()
        majors = majors_resp.get("majors", [])
    except requests.exceptions.RequestException:
        st.error("❌ Could not fetch majors list from API")
        majors = []

    if majors:
        major_name = st.selectbox("Select major/department", majors)
    else:
        st.info("No majors available or failed to load majors list")

else:
    students_only = st.checkbox("Students only (filter)", value=False)

def build_query_params(start_date, end_date, interval, students_only=False):
    params = {"interval": interval}
    if start_date:
        params["start_date"] = start_date.isoformat()
    if end_date:
        params["end_date"] = end_date.isoformat()
    if students_only:
        params["students_only"] = "true"
    return params

def render_timeline(df: pd.DataFrame, interval: str):
    if df.empty:
        st.warning("No timeline data to display")
        return

    # Show summary metrics
    total_emissions = df["total_emissions_kg"].sum()
    total_periods = len(df)
    total_packages = df["package_count"].sum()
    total_trees_planted = df["total_trees_planted"].sum()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total emissions (kg CO2e)", f"{total_emissions:.2f}")
    m2.metric("Total packages", int(total_packages))
    m3.metric("Periods shown", int(total_periods))
    m4.metric("Equivalent trees planted", f"{total_trees_planted:.2f}")

    # Plot emissions over time
    try:
        plot_df = df.set_index("period")["package_count"].astype(float)
        st.area_chart(plot_df, x_label="Period", y_label="Number of Packages", use_container_width=True)
    except Exception:
        st.line_chart(df.set_index("period")["package_count"], x_label="Period", y_label="Number of Packages", use_container_width=True)

if scope == "By Major":
    if not major_name:
        st.error("Please select a major")
    else:
        params = build_query_params(start_date, end_date, interval)
        params["major_name"] = major_name
        try:
            r = requests.get(f"{API_BASE_URL}/timeline/major", params=params, timeout=8)
            r.raise_for_status()
            resp = r.json()
            timeline = resp.get("timeline", [])
            df = pd.DataFrame(timeline)
            # remove rows where period is missing/None so charts/tables don't show them
            if "period" in df.columns:
                df = df[df["period"].notnull() & (df["period"].astype(str) != "None")]
            if not df.empty:
                # ensure numeric types
                for col in ["total_emissions_kg", "avg_emissions_per_package_kg", "package_count", "total_trees_planted", "total_miles_driven"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            render_timeline(df, interval)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                st.warning("No data found for that major or date range")
            else:
                st.error("API error fetching major timeline")
        except requests.exceptions.RequestException:
            st.error("❌ Cannot connect to API")

else:
    params = build_query_params(start_date, end_date, interval, students_only=students_only)
    try:
        r = requests.get(f"{API_BASE_URL}/timeline/all", params=params, timeout=8)
        r.raise_for_status()
        resp = r.json()
        timeline = resp.get("timeline", [])
        df = pd.DataFrame(timeline)
        # remove rows where period is missing/None so charts/tables don't show them
        if "period" in df.columns:
            df = df[df["period"].notnull() & (df["period"].astype(str) != "None")]
        if not df.empty:
            for col in ["total_emissions_kg", "avg_emissions_per_package_kg", "package_count", "total_distance_km", "total_trees_planted", "total_miles_driven"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        render_timeline(df, interval)
    except requests.exceptions.HTTPError as e:
        st.error("API returned an error when fetching timeline")
    except requests.exceptions.RequestException:
        st.error("❌ Cannot connect to API")