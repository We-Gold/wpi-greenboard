import streamlit as st
import pandas as pd
import requests
import os

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Details", page_icon="📦")

selected_student = st.session_state.get("selected_student", None)

if selected_student:
    st.markdown(f"# {selected_student['name']}")
    if 'major' in selected_student and selected_student['major'] is not None:
        st.markdown(f"### {selected_student['major']} Major")
else:
    st.markdown("# Student Details")
    st.markdown("### No student selected")

# Package data format:
# PackageRead(
#     package_id=r[0],
#     tracking_number=r[1],
#     carrier_name=r[2],
#     service_type=r[3],
#     date_shipped=r[4],
#     total_emissions_kg=r[5],
#     distance_traveled=r[6]
# )

try:
    if selected_student and "wpi_id" in selected_student:
        df = pd.DataFrame(requests.get(f"{API_BASE_URL}/packages/student/{selected_student['wpi_id']}").json())
        timeline_data = requests.get(f"{API_BASE_URL}/timeline/person/{selected_student['wpi_id']}?interval=day").json()
    else:
        df = pd.DataFrame()
        timeline_data = None
except requests.exceptions.RequestException:
    st.error("❌ Cannot connect to API")
    df = pd.DataFrame()

# Assign emissions constants based on transport mode, carrier, and weight
transit_emission_factors = {
    "Air": 2.0,    # kg CO2 per lb
    "Ground": 1.0, # kg CO2 per lb
    "Ship": 0.5    # kg CO2 per lb
}

weight_emission_factors = {
    (0, 2): 1.0,     # 0 < weight ≤ 2 lbs
    (2, 5): 1.5,     # 2 < weight ≤ 5 lbs
    (5, 10): 2.0,    # 5 < weight ≤ 10 lbs
    (10, float('inf')): 2.5  # weight > 10 lbs
}


if not df.empty:
    # Show a timeline view of each package, where each has a card with its details, including a formula showing how the carbon emissions were calculated
    st.markdown("## Package Delivery Timeline")

    if timeline_data is not None and "timeline" in timeline_data:
        timeline_df = pd.DataFrame(timeline_data["timeline"])

        # Skip any where the period is null or empty
        if "period" in timeline_df.columns:
            timeline_df = timeline_df[timeline_df["period"].notnull() & (timeline_df["period"].astype(str) != "None")]

        if timeline_df.shape[0] > 1:
            # Add empty rows for any missing periods in the timeline
            timeline_df['period'] = pd.to_datetime(timeline_df['period'])
            timeline_df = timeline_df.set_index('period').resample('D').asfreq().fillna(0).reset_index()
            timeline_df['period'] = timeline_df['period'].dt.strftime('%Y-%m-%d')

            # Plot the timeline of emissions over time
            st.area_chart(timeline_df.set_index('period')['package_count'], height=300, width=700, x_label="Period", y_label="Number of Packages", use_container_width=True)


    # Convert dates to datetime for proper sorting
    df['date_shipped'] = pd.to_datetime(df['date_shipped'])
    df_sorted = df.sort_values('date_shipped', ascending=False)

    i = 0

    for index, row in df_sorted.iterrows():            
        # Skip entries with missing data
        if pd.isnull(row['total_emissions_kg']):
            continue

        try:
            date_shipped = row['date_shipped'].strftime('%B %d, %Y')
        except Exception:
            date_shipped = "Unknown Date"

        i += 1

        # Card container with border styling
        with st.container(border=True):
            # Header with date and package number prominently displayed
            st.markdown(f"### 📦 Package {i}")
            st.caption(f"Delivered on {date_shipped}")
            
            # Package details in a clean layout
            col_details1, col_details2 = st.columns(2)
            
            with col_details1:
                # st.markdown(f"**Distance:** {row['distance_traveled']} km")
                st.metric("Distance", row['distance_traveled'])
                # st.metric("Weight", f"{row['Weight (lbs)']} lbs")
                st.metric("Carrier", row['carrier_name'])
            
            with col_details2:
                # st.write(row)
                st.metric("Transport Mode", row['service_type'])
                st.metric("Carbon Emissions", f"{row['total_emissions_kg']:.2f} kg CO2e")

            # with st.expander("📍 View Route Details", expanded=False):
                # st.markdown(f"**Source:** {row['Source']}")
                # st.markdown(f"**Destination:** {row['Desitination']}")
                # st.markdown(f"**Distance:** {row['distance_traveled']} km")

            # with st.expander("🚛 Emission Breakdown", expanded=False):
            #     st.markdown(f"**Main Transit Emissions:** {row['Main Transit Emissions (kg CO2e)']:.4f} kg CO2e")
            #     st.markdown(f"**Last Mile Emissions:** {row['Last Mile Emissions (kg CO2e)']:.4f} kg CO2e")

            with st.expander("🌳 Environmental Impact", expanded=False):
                st.markdown(f"**Equivalent Trees Planted:** {row['equivalent_trees_planted']:.2f}")
                st.markdown(f"**Equivalent Miles Driven:** {row['equivalent_miles_driven']:.2f} miles")

        st.markdown("<br>", unsafe_allow_html=True)

    # Add an alert at the bottom indicating the number of packages that weren't shown due to missing data
    missing_data_count = df['total_emissions_kg'].isnull().sum()
    if missing_data_count > 0:
        st.warning(f"⚠️ {missing_data_count} packages were not shown due to missing emissions data.")