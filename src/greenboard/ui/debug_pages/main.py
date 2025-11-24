import streamlit as st
import requests
import os

# API configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="WPI Greenboard",
    page_icon="🏆",
)

st.title("WPI Greenboard")

# Health check
try:
    health_response = requests.get(f"{API_BASE_URL}/db/health")
    if health_response.status_code == 200:
        health_data = health_response.json()
        st.success("✅ Connected to API")
        st.write("Database time:", health_data["database_time"])
    else:
        st.error("❌ API connection failed")
except requests.exceptions.RequestException:
    st.error("❌ Cannot connect to API")

# Display tables
try:
    tables_response = requests.get(f"{API_BASE_URL}/db/tables")
    if tables_response.status_code == 200:
        tables_data = tables_response.json()
        st.write("Tables in the database:")
        for table in tables_data["tables"]:
            st.write("-", table)
except requests.exceptions.RequestException:
    st.error("Failed to fetch tables")