import streamlit as st
import pandas as pd
import requests
import os

# API configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="View Tables", page_icon="🗂️")

st.markdown("# View Tables")

# Fetch list of tables from the API
try:
    tables_response = requests.get(f"{API_BASE_URL}/db/tables")
    if tables_response.status_code == 200:
        tables_data = tables_response.json()
        table_names = tables_data["tables"]

        # Create a dropdown for table selection
        selected_table = st.selectbox("Select a table to view", table_names)

        if selected_table:
            st.write(f"Fetching data for table: **{selected_table}**")
            # Fetch data for the selected table
            try:
                table_data_response = requests.get(f"{API_BASE_URL}/db/tables/{selected_table}")
                if table_data_response.status_code == 200:
                    table_data = table_data_response.json()
                    df = pd.DataFrame(table_data)
                    st.dataframe(df)
                else:
                    st.error(
                        f"Failed to fetch data for table '{selected_table}'. Status code: {table_data_response.status_code}")
            except requests.exceptions.RequestException as e:
                st.error(f"An error occurred while fetching data for table '{selected_table}': {e}")

    else:
        st.error(f"Failed to fetch list of tables. Status code: {tables_response.status_code}")
except requests.exceptions.RequestException as e:
    st.error(f"An error occurred while fetching the list of tables: {e}")
