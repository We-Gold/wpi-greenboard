import streamlit as st
import requests
import os
from datetime import datetime
from typing import Optional

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Add Package")

st.markdown("# Add New Package")

# Tracking number lookup section
st.subheader("🔍 Lookup by Tracking Number")
st.info("Enter a tracking number to automatically extract package information from FedEx or UPS APIs")

lookup_col1, lookup_col2 = st.columns([3, 1])
with lookup_col1:
    lookup_tracking = st.text_input(
        "Tracking Number",
        placeholder="Enter tracking number (e.g., 1Z999AA10123456784 for UPS, 484078159554 for FedEx)",
        key="lookup_tracking",
        label_visibility="collapsed"
    )
with lookup_col2:
    lookup_button = st.button("🔍 Lookup", use_container_width=True, type="primary")

if lookup_button and lookup_tracking:
    with st.spinner("Looking up tracking information..."):
        try:
            lookup_response = requests.post(
                f"{API_BASE_URL}/packages/lookup-tracking",
                json={"tracking_number": lookup_tracking, "production": False},
                timeout=30
            )
            
            if lookup_response.status_code == 200:
                lookup_data = lookup_response.json()
                st.success("✅ Package information retrieved successfully!")
                
                # Store in session state to pre-fill form
                st.session_state.lookup_data = lookup_data
                st.session_state.tracking_number = lookup_data.get("tracking_number")
                st.session_state.carrier_name = lookup_data.get("carrier")
                st.session_state.service_type = lookup_data.get("service_type")
                st.session_state.weight_kg = lookup_data.get("weight_kg")
                st.session_state.distance_traveled = lookup_data.get("distance_km")
                st.session_state.total_emissions_kg = lookup_data.get("total_emissions_kg")
                # Note: recipient_id is not set from lookup - user must select it
                
                # Display retrieved information
                with st.expander("📦 Retrieved Package Information", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Carrier:** {lookup_data.get('carrier', 'N/A')}")
                        st.write(f"**Service Type:** {lookup_data.get('service_type', 'N/A')}")
                        st.write(f"**Weight:** {lookup_data.get('weight_kg', 0):.2f} kg")
                    with col2:
                        distance_km = lookup_data.get('distance_km', 0)
                        is_default = lookup_data.get('is_default_distance', False)
                        distance_display = f"{distance_km:.2f} km"
                        if is_default:
                            distance_display += " ⚠️ (estimated)"
                        st.write(f"**Distance:** {distance_display}")
                        st.write(f"**Emissions:** {lookup_data.get('total_emissions_kg', 0):.4f} kg CO2e")
                        st.write(f"**Transport Mode:** {lookup_data.get('transport_mode', 'N/A')}")
                        
                        if is_default:
                            st.warning("⚠️ Distance is an estimate (geocoding failed). Actual distance may vary.")
                    
                    if lookup_data.get('origin'):
                        st.write(f"**Origin:** {lookup_data['origin'].get('city', '')}, {lookup_data['origin'].get('state', '')} {lookup_data['origin'].get('postal_code', '')}")
                    if lookup_data.get('destination'):
                        st.write(f"**Destination:** {lookup_data['destination'].get('city', '')}, {lookup_data['destination'].get('state', '')} {lookup_data['destination'].get('postal_code', '')}")
                
                st.info("💡 Information has been pre-filled in the form below. You can edit any fields before submitting.")
                st.rerun()
            else:
                error_detail = lookup_response.json().get("detail", "Unknown error")
                st.error(f"❌ {error_detail}")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Could not connect to API: {e}")

st.divider()

# Fetch available carriers and service types
try:
    carriers_response = requests.get(f"{API_BASE_URL}/packages/carriers", timeout=6)
    carriers_response.raise_for_status()
    carriers_data = carriers_response.json()
    carrier_names = [c["carrier_name"] for c in carriers_data]
except requests.exceptions.RequestException:
    st.error("❌ Could not fetch carriers from API")
    carrier_names = ["Other"]

try:
    service_types_response = requests.get(f"{API_BASE_URL}/packages/service-types", timeout=6)
    service_types_response.raise_for_status()
    service_types_data = service_types_response.json()
    service_type_options = [""] + [st["service_type"] for st in service_types_data]
    service_type_factors = {st["service_type"]: st["emission_factor"] for st in service_types_data if st["emission_factor"]}
except requests.exceptions.RequestException:
    st.warning("⚠️ Could not fetch service types from API")
    service_type_options = [""]
    service_type_factors = {}

# Fetch available persons/WPI IDs
try:
    persons_response = requests.get(f"{API_BASE_URL}/packages/persons", timeout=6)
    persons_response.raise_for_status()
    persons_data = persons_response.json()
    # Create a mapping for dropdown display: "Name (WPI_ID)"
    person_options = {f"{p['name']} ({p['wpi_id']})": p['wpi_id'] for p in persons_data}
    person_display_names = list(person_options.keys())
except requests.exceptions.RequestException:
    st.error("❌ Could not fetch persons from API")
    person_options = {}
    person_display_names = []

# Form for adding a new package
with st.form("add_package_form"):
    st.subheader("Package Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        tracking_number = st.text_input(
            "Tracking Number *",
            value=st.session_state.get("tracking_number", ""),
            placeholder="Enter tracking number",
            help="Unique tracking number for the package"
        )
        carrier_name = st.selectbox(
            "Carrier *",
            options=carrier_names,
            index=carrier_names.index(st.session_state.get("carrier_name", carrier_names[0])) if st.session_state.get("carrier_name") in carrier_names else 0,
            help="Select the shipping carrier"
        )
        service_type = st.selectbox(
            "Service Type",
            options=service_type_options,
            index=service_type_options.index(st.session_state.get("service_type", "")) if st.session_state.get("service_type") in service_type_options else 0,
            help="Optional: Select the service type (e.g., Ground, Air, Express)"
        )
    
    with col2:
        if person_display_names:
            # Get current selection from session state if available
            current_selection = st.session_state.get("recipient_display")
            default_index = 0
            if current_selection and current_selection in person_display_names:
                default_index = person_display_names.index(current_selection)
            
            selected_person_display = st.selectbox(
                "Recipient *",
                options=person_display_names,
                index=default_index,
                help="Select the recipient (WPI ID) for this package",
                key="recipient_select"
            )
            recipient_id = person_options[selected_person_display]
            # Store the display name in session state
            st.session_state.recipient_display = selected_person_display
        else:
            st.error("No recipients available. Please ensure persons are in the database.")
            recipient_id = None
        
        date_shipped = st.date_input(
            "Date Shipped",
            value=None,
            help="Optional: Date when the package was shipped"
        )
    
    st.subheader("Emissions Calculation")
    st.info("💡 Provide weight and distance to automatically calculate emissions. The calculation includes both main transit and last-mile delivery emissions using standardized emission factors.")
    
    col3, col4 = st.columns(2)
    
    with col3:
        weight_kg = st.number_input(
            "Weight (kg)",
            min_value=0.0,
            value=st.session_state.get("weight_kg"),
            step=0.1,
            help="Package weight in kilograms"
        )
    
    with col4:
        distance_traveled = st.number_input(
            "Distance Traveled (km)",
            min_value=0.0,
            value=st.session_state.get("distance_traveled"),
            step=1.0,
            help="Distance traveled in kilometers"
        )
    
    # Show emission factor info if service type is selected
    if service_type and service_type in service_type_factors:
        emission_factor = service_type_factors[service_type]
        st.info(f"📊 Emission factor for '{service_type}': {emission_factor} kg CO2e per tonne-km")
    
    # Preview calculation if both weight and distance are provided
    if weight_kg and distance_traveled and weight_kg > 0 and distance_traveled > 0:
        # Use emission factor from service type if available, otherwise default
        emission_factor = service_type_factors.get(service_type, 0.127)  # Default to truck_average
        
        weight_tonnes = weight_kg / 1000
        calculated_emissions = weight_tonnes * distance_traveled * emission_factor
        
        st.success(f"📦 **Estimated Emissions:** {calculated_emissions:.4f} kg CO2e")
        
        # Show equivalent metrics
        trees_planted = calculated_emissions / 21.0
        miles_driven = calculated_emissions / 0.404
        
        col5, col6 = st.columns(2)
        with col5:
            st.metric("Equivalent Trees Planted", f"{trees_planted:.2f}")
        with col6:
            st.metric("Equivalent Miles Driven", f"{miles_driven:.2f}")
    
    submitted = st.form_submit_button("Add Package", use_container_width=True)
    
    if submitted:
        # Validation
        if not tracking_number:
            st.error("❌ Tracking number is required")
        elif not carrier_name:
            st.error("❌ Carrier is required")
        elif not recipient_id:
            st.error("❌ Recipient is required")
        else:
            # Prepare data
            package_data = {
                "tracking_number": tracking_number,
                "carrier_name": carrier_name,
                "recipient_id": recipient_id,  # Required
            }
            
            # Add optional fields only if they have values
            if service_type:
                package_data["service_type"] = service_type
            if date_shipped:
                # Convert date to datetime string format
                package_data["date_shipped"] = datetime.combine(date_shipped, datetime.min.time()).isoformat()
            if weight_kg and weight_kg > 0:
                package_data["weight_kg"] = weight_kg
            if distance_traveled and distance_traveled > 0:
                package_data["distance_traveled"] = distance_traveled
            
            # Submit to API
            try:
                response = requests.post(
                    f"{API_BASE_URL}/packages/",
                    json=package_data,
                    timeout=10
                )
                
                if response.status_code == 200:
                    created_package = response.json()
                    st.success("✅ Package added successfully!")
                    
                    # Clear session state after successful submission
                    for key in ["lookup_data", "tracking_number", "carrier_name", "service_type", "weight_kg", "distance_traveled", "total_emissions_kg"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    
                    # Display created package info
                    st.json(created_package)
                    
                    # Show emissions info if calculated
                    if created_package.get("total_emissions_kg"):
                        st.balloons()
                        st.info(
                            f"🌱 This package's emissions are equivalent to "
                            f"{created_package.get('equivalent_trees_planted', 0):.2f} trees planted or "
                            f"{created_package.get('equivalent_miles_driven', 0):.2f} miles driven"
                        )
                elif response.status_code == 400:
                    error_detail = response.json().get("detail", "Bad request")
                    st.error(f"❌ {error_detail}")
                else:
                    st.error(f"❌ Failed to add package. Status code: {response.status_code}")
                    st.json(response.json())
                    
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Could not connect to API: {e}")

# Instructions section
with st.expander("📖 How to use this form"):
    st.markdown("""
    ### Required Fields
    - **Tracking Number**: The unique tracking number for the package
    - **Carrier**: The shipping carrier (e.g., UPS, FedEx, USPS)
    
    ### Optional Fields
    - **Service Type**: The shipping service type (e.g., Ground, Air, Express)
    - **Recipient WPI ID**: The WPI ID of the person receiving the package
    - **Date Shipped**: When the package was shipped
    
    ### Emissions Calculation
    To automatically calculate emissions, provide:
    - **Weight (kg)**: The weight of the package in kilograms
    - **Distance Traveled (km)**: The distance the package traveled in kilometers
    
    The system will:
    1. Look up the emission factor for the selected service type (or use a default)
    2. Calculate emissions using the formula: `(weight_kg / 1000) × distance_km × emission_factor`
    3. Automatically calculate equivalent trees planted and miles driven
    
    ### Notes
    - If you don't provide weight and distance, the package will be created without emissions data
    - You can add emissions data later by updating the package
    - The tracking number must be unique
    """)

