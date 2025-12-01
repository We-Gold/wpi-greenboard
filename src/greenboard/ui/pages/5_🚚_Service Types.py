import streamlit as st
import pandas as pd
import requests
import os
import altair as alt

st.set_page_config(page_title="Service Types", page_icon="🚚")

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1000px !important;
        padding-left: 3rem;
        padding-right: 3rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.markdown("# 🚚 Service Types")
st.markdown("Average emissions per package by shipping service type")

st.sidebar.header("Service Type Controls")

viz_options = ["Table", "Bar Chart"]
viz_mode = st.sidebar.selectbox("Visualization", viz_options, index=0)

view_options = ["Overall", "By Major", "By Class Year"]
view_mode = st.sidebar.selectbox("View", view_options, index=0)

def safe_get_json(url: str):
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException:
        st.error(f"❌ Cannot connect to API at `{url}`")
        return None


if view_mode == "Overall":
    min_package_count = st.sidebar.number_input(
        "Minimum package count",
        min_value=0,
        value=0,
        step=1
    )

    st.subheader("Overall: Average Emissions per Package by Service Type")

    data = safe_get_json(f"{API_BASE_URL}/service-types/overall")
    if not data or "rows" not in data:
        st.stop()

    df = pd.DataFrame(data["rows"])

    if df.empty:
        st.info("No service type data available.")
        st.stop()

    if "percent_of_all_packages" in df.columns:
        df = df.drop(columns=["percent_of_all_packages"])

    df = df[df["package_count"] >= min_package_count]

    if df.empty:
        st.info("No service types meet the minimum package count.")
        st.stop()

    df = df.sort_values("avg_emissions_per_package_kg", ascending=False)
    df["Rank"] = range(1, len(df) + 1)

    df_display = df.rename(
        columns={
            "Rank": "Rank",
            "service_type": "Service Type",
            "package_count": "Package Count",
            "total_emissions_kg": "Total Emissions (kg CO2e)",
            "avg_emissions_per_package_kg": "Avg Emissions per Package (kg CO2e)",
        }
    )

    if viz_mode == "Table":
        df_table = df_display[
            [
                "Rank",
                "Service Type",
                "Package Count",
                "Total Emissions (kg CO2e)",
                "Avg Emissions per Package (kg CO2e)",
            ]
        ].set_index("Rank")

        num_cols = df_table.select_dtypes(include=["float", "int"]).columns
        styled = df_table.style.format(
            {col: "{:g}".format for col in num_cols}
        ).set_properties(
            subset=["Avg Emissions per Package (kg CO2e)"],
            **{"background-color": "#333542"}
        )

        st.dataframe(styled, use_container_width=True)
    else:
        chart = (
            alt.Chart(df_display)
            .mark_bar()
            .encode(
                x=alt.X(
                    "Service Type",
                    sort="-y",
                ),
                y="Avg Emissions per Package (kg CO2e)",
                tooltip=[
                    "Rank",
                    "Service Type",
                    "Avg Emissions per Package (kg CO2e)",
                    "Package Count",
                    "Total Emissions (kg CO2e)",
                ],
            )
            .interactive()
        )
        st.altair_chart(chart, use_container_width=True)


elif view_mode == "By Major":
    st.subheader("Average Emissions per Package by Service Type by Major")

    data = safe_get_json(f"{API_BASE_URL}/service-types/by-major?students_only=true")
    if not data or "rows" not in data:
        st.stop()

    df = pd.DataFrame(data["rows"])

    if df.empty:
        st.info("No service type data available by major.")
        st.stop()

    majors = sorted(df["major"].dropna().unique().tolist())
    selected_major = st.sidebar.selectbox("Filter by Major", majors)

    min_package_count = st.sidebar.number_input(
        "Minimum package count",
        min_value=0,
        value=0,
        step=1
    )

    df_major = df[df["major"] == selected_major].copy()
    df_major = df_major[df_major["package_count"] >= min_package_count]

    if df_major.empty:
        st.info("No service types meet the minimum package count for this major.")
        st.stop()

    df_major = df_major.sort_values("avg_emissions_per_package_kg", ascending=False)
    df_major["Rank"] = range(1, len(df_major) + 1)

    df_display = df_major.rename(
        columns={
            "major": "Major",
            "service_type": "Service Type",
            "package_count": "Package Count",
            "total_emissions_kg": "Total Emissions (kg CO2e)",
            "avg_emissions_per_package_kg": "Avg Emissions per Package (kg CO2e)",
        }
    )

    st.markdown(f"**Major:** {selected_major}")

    if viz_mode == "Table":
        df_table = df_display[
            [
                "Rank",
                "Service Type",
                "Package Count",
                "Total Emissions (kg CO2e)",
                "Avg Emissions per Package (kg CO2e)",
            ]
        ].set_index("Rank")

        num_cols = df_table.select_dtypes(include=["float", "int"]).columns
        styled = df_table.style.format(
            {col: "{:g}".format for col in num_cols}
        ).set_properties(
            subset=["Avg Emissions per Package (kg CO2e)"],
            **{"background-color": "#333542"}
        )

        st.dataframe(styled, use_container_width=True)
    else:
        chart = (
            alt.Chart(df_display)
            .mark_bar()
            .encode(
                x=alt.X("Service Type", sort="-y"),
                y="Avg Emissions per Package (kg CO2e)",
                tooltip=[
                    "Rank",
                    "Major",
                    "Service Type",
                    "Avg Emissions per Package (kg CO2e)",
                    "Package Count",
                    "Total Emissions (kg CO2e)",
                ],
            )
            .interactive()
        )
        st.altair_chart(chart, use_container_width=True)


elif view_mode == "By Class Year":
    st.subheader("Average Emissions per Package by Service Type by Class Year")

    data = safe_get_json(f"{API_BASE_URL}/service-types/by-class-year?students_only=true")
    if not data or "rows" not in data:
        st.stop()

    df = pd.DataFrame(data["rows"])

    if df.empty:
        st.info("No service type data available by class year.")
        st.stop()

    year_groups = sorted(df["class_year_group"].dropna().unique().tolist())
    selected_year = st.sidebar.selectbox("Filter by Class Year", year_groups)

    min_package_count = st.sidebar.number_input(
        "Minimum package count",
        min_value=0,
        value=0,
        step=1
    )

    df_year = df[df["class_year_group"] == selected_year].copy()
    df_year = df_year[df_year["package_count"] >= min_package_count]

    if df_year.empty:
        st.info("No service types meet the minimum package count for this class year group.")
        st.stop()

    df_year = df_year.sort_values("avg_emissions_per_package_kg", ascending=False)
    df_year["Rank"] = range(1, len(df_year) + 1)

    df_display = df_year.rename(
        columns={
            "class_year_group": "Class Year Group",
            "service_type": "Service Type",
            "package_count": "Package Count",
            "total_emissions_kg": "Total Emissions (kg CO2e)",
            "avg_emissions_per_package_kg": "Avg Emissions per Package (kg CO2e)",
        }
    )

    st.markdown(f"**Class Year Group:** {selected_year}")

    if viz_mode == "Table":
        df_table = df_display[
            [
                "Rank",
                "Service Type",
                "Package Count",
                "Total Emissions (kg CO2e)",
                "Avg Emissions per Package (kg CO2e)",
            ]
        ].set_index("Rank")

        num_cols = df_table.select_dtypes(include=["float", "int"]).columns
        styled = df_table.style.format(
            {col: "{:g}".format for col in num_cols}
        ).set_properties(
            subset=["Avg Emissions per Package (kg CO2e)"],
            **{"background-color": "#333542"}
        )

        st.dataframe(styled, use_container_width=True)
    else:
        chart = (
            alt.Chart(df_display)
            .mark_bar()
            .encode(
                x=alt.X("Service Type", sort="-y"),
                y="Avg Emissions per Package (kg CO2e)",
                tooltip=[
                    "Rank",
                    "Class Year Group",
                    "Service Type",
                    "Avg Emissions per Package (kg CO2e)",
                    "Package Count",
                    "Total Emissions (kg CO2e)",
                ],
            )
            .interactive()
        )
        st.altair_chart(chart, use_container_width=True)

