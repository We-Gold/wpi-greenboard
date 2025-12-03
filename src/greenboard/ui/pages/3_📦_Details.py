import streamlit as st
import pandas as pd
import requests
import os
import plotly.express as px

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
                st.metric("Distance", f"{row['distance_traveled']:.2f} miles")
                st.metric("Carrier", row['carrier_name'])
            
            with col_details2:
                st.metric("Transport Mode", row['service_type'])
                st.metric("Carbon Emissions", f"{row['total_emissions_kg']:.2f} kg CO2e")

            with st.expander("🌳 Environmental Impact", expanded=False):
                st.markdown(f"**Equivalent Trees Planted:** {row['equivalent_trees_planted']:.2f}")
                st.markdown(f"**Equivalent Miles Driven:** {row['equivalent_miles_driven']:.2f} miles")

            # Add a button to show calculation details
            with st.expander("🧮 Emissions Calculation Details", expanded=False):
                try:
                    calc_details_response = requests.get(f"{API_BASE_URL}/emissions/package/{row['package_id']}/calculation-details")
                    if calc_details_response.status_code == 200:
                        calc_details = calc_details_response.json()
                        
                        st.markdown("**Calculation Inputs:**")
                        for key, value in calc_details['calculation_inputs'].items():
                            st.markdown(f"- **{key.replace('_', ' ').title()}:** {value}")

                        st.markdown("**Calculation Steps:**")
                        for step_key, step in calc_details['calculation_steps'].items():
                            st.markdown(f"**{step['description']}**")
                            st.markdown(f"Formula: `{step['formula']}`")
                            st.markdown(f"Calculation: `{step['calculation']}`")
                            st.markdown(f"Result: **{step['result']}**")
                            st.markdown("---")
                    else:
                        st.error(f"Failed to fetch calculation details. Status code: {calc_details_response.status_code}")
                except requests.exceptions.RequestException:
                    st.error("❌ Cannot connect to API to fetch calculation details")

        st.markdown("<br>", unsafe_allow_html=True)

    # Add an alert at the bottom indicating the number of packages that weren't shown due to missing data
    missing_data_count = df['total_emissions_kg'].isnull().sum()
    if missing_data_count > 0:
        st.warning(f"⚠️ {missing_data_count} packages were not shown due to missing emissions data.")

# Carrier Stats Section at the bottom (toggleable)
if selected_student and "wpi_id" in selected_student:
    st.markdown("---")
    
    # Toggle button for carrier stats
    if st.button("Get Carrier Stats", key="carrier_stats_btn"):
        st.session_state.show_carrier_stats = not st.session_state.get("show_carrier_stats", False)
        st.rerun()
    
    # Display carrier stats if toggled on
    if st.session_state.get("show_carrier_stats", False):
        try:
            carrier_stats_response = requests.get(f"{API_BASE_URL}/packages/student/{selected_student['wpi_id']}/carrier-stats")
            if carrier_stats_response.status_code == 200:
                carrier_stats = carrier_stats_response.json()
                
                if carrier_stats:
                    # Create DataFrame for better display
                    stats_df = pd.DataFrame(carrier_stats)
                    
                    # Display Carrier Usage Frequency chart with hover tooltips
                    st.markdown("### Carrier Usage Frequency")
                    
                    # Create Plotly bar chart with custom hover text
                    fig = px.bar(
                        stats_df,
                        x='carrier_name',
                        y='frequency_percentage',
                        labels={
                            'carrier_name': 'Carrier',
                            'frequency_percentage': 'Frequency (%)'
                        },
                        text='frequency_percentage',
                        hover_data={
                            'carrier_name': True,
                            'frequency_percentage': ':.1f',
                            'package_count': True
                        },
                        custom_data=['package_count']
                    )
                    
                    # Customize hover template to show both package count and percentage
                    fig.update_traces(
                        hovertemplate='<b>%{x}</b><br>' +
                                    'Frequency: %{y:.1f}%<br>' +
                                    'Package Count: %{customdata[0]}<br>' +
                                    '<extra></extra>',
                        texttemplate='%{y:.1f}%',
                        textposition='outside'
                    )
                    
                    # Update layout
                    fig.update_layout(
                        xaxis_title='Carrier',
                        yaxis_title='Frequency (%)',
                        showlegend=False,
                        height=400,
                        margin=dict(l=20, r=20, t=20, b=20)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                else:
                    st.info("No carrier statistics available. This student has no packages.")
            elif carrier_stats_response.status_code == 404:
                st.warning("Student not found.")
            else:
                st.error(f"Failed to fetch carrier stats. Status code: {carrier_stats_response.status_code}")
        except requests.exceptions.RequestException:
            st.error("❌ Cannot connect to API to fetch carrier stats")