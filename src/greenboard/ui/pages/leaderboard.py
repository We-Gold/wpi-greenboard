import streamlit as st
import pandas as pd
import requests
import os

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.markdown("# 🌱 WPI Greenboard")
st.markdown("2025-2026 Academic Year")

# Add controls for filtering, number of entries per page, pagination, and search
st.sidebar.header("Leaderboard Controls")

# View mode dropdown
view_options = ["By Student", "By Major"]
view_mode = st.sidebar.selectbox("View Mode", view_options, index=0)  # Default to "By Student"
group_by_major = (view_mode == "By Major")

# Number of entries dropdown
entries_options = [5, 10, 15, 20, 25]
num_entries = st.sidebar.selectbox("Entries per page", entries_options, index=1)  # Default to 10

# Display the leaderboard
if group_by_major:
    st.subheader("Emissions by Major (Oct 2025)")

    try:
        major_stats = pd.DataFrame(requests.get(f"{API_BASE_URL}/leaderboard/majors/").json()) 
    except requests.exceptions.RequestException:
        st.error("❌ Cannot connect to API")
        major_stats = pd.DataFrame()  # Create an empty DataFrame in case of error

    # Rename columns
    major_stats = major_stats.rename(columns={
        "rank": "Rank",
        "major": "Major",
        "carbon_emissions_kg": "Total Emissions (kg CO2e)"
    })

    # Pagination for major stats
    total_majors = len(major_stats)
    total_pages = (total_majors - 1) // num_entries + 1
    
    # Get current page from session state or default to 1
    if 'major_page' not in st.session_state:
        st.session_state.major_page = 1
    
    page = st.session_state.major_page
    start_idx = (page - 1) * num_entries
    end_idx = start_idx + num_entries
    display_major_stats = major_stats.iloc[start_idx:end_idx].copy()
    display_major_stats = display_major_stats.set_index("Rank")
    
    # Show pagination info and table
    if total_pages > 1:
        st.write(f"Showing majors {start_idx + 1}-{min(end_idx, total_majors)} of {total_majors}")

    st.table(display_major_stats)

    # Page selector below the table
    if total_pages > 1:
        col1, col2, col3, col4, col5 = st.columns([1, 2, 3, 2, 1])
        
        with col2:
            if st.button("← Previous", disabled=(page <= 1), key="major_prev", use_container_width=True):
                st.session_state.major_page = page - 1
                st.rerun()
        
        with col3:
            new_page = st.selectbox("Page", range(1, total_pages + 1), index=page-1, key="major_page_selector", label_visibility="collapsed")
            if new_page != st.session_state.major_page:
                st.session_state.major_page = new_page
                st.rerun()
        
        with col4:
            if st.button("Next →", disabled=(page >= total_pages), key="major_next", use_container_width=True):
                st.session_state.major_page = page + 1
                st.rerun()
else:
    st.subheader("Highest Emissions by Student (Oct 2025)")

    try:
        df = pd.DataFrame(requests.get(f"{API_BASE_URL}/leaderboard/students/").json()) 
    except requests.exceptions.RequestException:
        st.error("❌ Cannot connect to API")
        df = pd.DataFrame()  # Create an empty DataFrame in case of error

    # Filter by major
    majors = ["All"] + sorted(df["major"].unique().tolist())
    selected_major = st.sidebar.selectbox("Filter by Major", majors)

    # Filter by major
    if selected_major != "All":
        try:
            df = pd.DataFrame(requests.get(f"{API_BASE_URL}/leaderboard/students/?major={selected_major}").json()) 
        except requests.exceptions.RequestException:
            st.error("❌ Cannot connect to API")
            df = pd.DataFrame()  # Create an empty DataFrame in case of error
    else:
        try:
            df = pd.DataFrame(requests.get(f"{API_BASE_URL}/leaderboard/students/").json()) 
        except requests.exceptions.RequestException:
            st.error("❌ Cannot connect to API")
            df = pd.DataFrame()  # Create an empty DataFrame in case of error

    # Rename columns
    df = df.rename(columns={
        "rank": "Rank",
        "name": "Name",
        "carbon_emissions_kg": "Carbon Emissions (kg CO2e)",
        "major": "Major"
    })

    # Pagination for student data
    total_students = len(df)
    total_pages = (total_students - 1) // num_entries + 1
    
    # Get current page from session state or default to 1
    if 'student_page' not in st.session_state:
        st.session_state.student_page = 1
    
    page = st.session_state.student_page
    start_idx = (page - 1) * num_entries
    end_idx = start_idx + num_entries
    display_df = df.iloc[start_idx:end_idx].copy()
    display_df = display_df.set_index("Rank")

    # Show pagination info
    if total_pages > 1:
        st.write(f"Showing students {start_idx + 1}-{min(end_idx, total_students)} of {total_students}")

    # Render table-like rows where clicking the student's name navigates to a details page
    # We'll render each row as columns with a clickable button so we can set query params
    st.write("")
    # Header row
    c_rank, c_name, c_emissions, c_action = st.columns([1, 4, 3, 2])
    # c_rank, c_name, c_major, c_emissions, c_action = st.columns([1, 4, 3, 3, 2])
    c_rank.markdown("**Rank**")
    c_name.markdown("**Name**")
    # c_major.markdown("**Major**")
    c_emissions.markdown("**Carbon Emissions (kg CO2e)**")
    c_action.markdown("**Details**")

    for idx, row in display_df.reset_index().iterrows():
        rank = row["Rank"]
        name = row.get("Name", "")
        # major = row.get("Major", "")
        emissions = row.get("Carbon Emissions (kg CO2e)", "")

        c_rank, c_name, c_emissions, c_action = st.columns([1, 4, 3, 2])
        # c_rank, c_name, c_major, c_emissions, c_action = st.columns([1, 4, 3, 3, 2])
        c_rank.write(rank)
        c_name.write(name)
        # c_major.write(major)
        c_emissions.write(emissions)

        # Provide an explicit "View" button in the action column for clarity/accessibility
        action_key = f"student_view_{rank}_{idx}"
        if c_action.button("View", key=action_key):
            # Set session storage variables for the selected student
            st.session_state.selected_student = {
                "rank": rank,
                "name": name,
                # "major": major,
                "wpi_id": row.get("wpi_id", None)
            }
            st.switch_page("pages/details.py")
    
    # Page selector below the table
    if total_pages > 1:
        col1, col2, col3, col4, col5 = st.columns([1, 2, 3, 2, 1])
        
        with col2:
            if st.button("← Previous", disabled=(page <= 1), key="student_prev", use_container_width=True):
                st.session_state.student_page = page - 1
                st.rerun()
        
        with col3:
            new_page = st.selectbox("Page", range(1, total_pages + 1), index=page-1, key="student_page_selector", label_visibility="collapsed")
            if new_page != st.session_state.student_page:
                st.session_state.student_page = new_page
                st.rerun()
        
        with col4:
            if st.button("Next →", disabled=(page >= total_pages), key="student_next", use_container_width=True):
                st.session_state.student_page = page + 1
                st.rerun()

# Footer
st.markdown("---")
st.markdown("Developed by WPI Greenboard Team for CS 542 - Database Management Systems")