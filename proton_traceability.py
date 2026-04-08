import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from st_aggrid import AgGrid, GridOptionsBuilder
import time
import os
from datetime import datetime

st.set_page_config(page_title="Proton Production Traceability", layout="wide")

LINE_URLS = {
    "Trim": "http://10.200.28.208/dashboards/#/?dashboard=53f11920-e1af-11ee-a41a-194721b4211b&period=today&lineLayoutItem=ae96d860-bf59-11ee-bc35-29118d9fcb94",
    "Final": "http://10.200.28.208/dashboards/#/?dashboard=53f11920-e1af-11ee-a41a-194721b4211b&period=today&lineLayoutItem=6177cda0-bf59-11ee-bc35-29118d9fcb94",
    "Chassis": "http://10.200.28.208/dashboards/#/?dashboard=53f11920-e1af-11ee-a41a-194721b4211b&period=today&lineLayoutItem=c2240880-bf59-11ee-bc35-29118d9fcb94",
    "Engine Sub": "http://10.200.28.208/dashboards/#/?dashboard=53f11920-e1af-11ee-a41a-194721b4211b&period=today&lineLayoutItem=e06abc30-bf59-11ee-bc35-29118d9fcb94",
    "Fr Sub": "http://10.200.28.208/dashboards/#/?dashboard=53f11920-e1af-11ee-a41a-194721b4211b&period=today&lineLayoutItem=fdbcafa0-bf59-11ee-bc35-29118d9fcb94",
    "Loop Sub": "http://10.200.28.208/dashboards/#/?dashboard=53f11920-e1af-11ee-a41a-194721b4211b&period=today&lineLayoutItem=0b4c5da0-bf5a-11ee-bc35-29118d9fcb94",
    "PC Line": "http://10.200.28.208/dashboards/#/?dashboard=53f11920-e1af-11ee-a41a-194721b4211b&period=today&lineLayoutItem=19f591f0-bf5a-11ee-bc35-29118d9fcb94",
    "RS Line": "http://10.200.28.208/dashboards/#/?dashboard=53f11920-e1af-11ee-a41a-194721b4211b&period=today&lineLayoutItem=26d4b4a0-bf5a-11ee-bc35-29118d9fcb94",
    "New Project": "http://10.200.28.208/dashboards/#/?dashboard=53f11920-e1af-11ee-a41a-194721b4211b&period=today&lineLayoutItem=3aa286c0-cdd6-11ef-be03-2107e4aeaf7d"
}

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--mute-audio")
    
    # Path logic for Streamlit Cloud vs Local
    if os.path.exists("/usr/bin/chromium"):
        options.binary_location = "/usr/bin/chromium"
    elif os.path.exists("/usr/bin/chromium-browser"):
        options.binary_location = "/usr/bin/chromium-browser"
        
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        st.error(f"Chromium Init Failed: {e}")
        return None

def scrape_line_data(selected_lines):
    driver = get_driver()
    if not driver: return pd.DataFrame()
        
    all_data = []
    status_text = st.empty()
    bar = st.progress(0)
    
    for i, line_name in enumerate(selected_lines):
        url = LINE_URLS[line_name]
        status_text.text(f"🚀 Scanning {line_name} Line (Collecting records)...")
        try:
            driver.get(url)
            # Higher wait time for large factory datasets to finish rendering
            time.sleep(15) 
            
            rows = driver.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                cells = row.find_elements(By.CLASS_NAME, "text-start")
                if len(cells) >= 6:
                    all_data.append({
                        "Line": line_name,
                        "Controller": cells[2].text.strip(),
                        "VIN": cells[5].text.strip(),
                        "Status": cells[0].text.strip(),
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
        except Exception as e:
            st.error(f"Error on {line_name}: {e}")
        bar.progress((i + 1) / len(selected_lines))
    
    driver.quit()
    return pd.DataFrame(all_data)

# --- UI LAYOUT ---
st.title("🛡️ Proton Global Traceability Matrix")
st.markdown(f"**Current Session:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

selected_lines = st.multiselect("Select Lines to Audit:", options=list(LINE_URLS.keys()), default=["Trim", "Final"])

if st.button("Run Global Cross-Check"):
    if not selected_lines:
        st.warning("Please select at least one line.")
    else:
        with st.spinner("Processing Large Dataset... Please wait."):
            df = scrape_line_data(selected_lines)
            
        if not df.empty:
            # PIVOT LOGIC: VIN is Y-axis, Controller is X-axis
            matrix = df.pivot_table(
                index='VIN', 
                columns=['Line', 'Controller'], 
                values='Status', 
                aggfunc='first'
            ).reset_index()

            # --- METRICS ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Total VINs Tracked", len(matrix))
            col2.metric("Controllers Audited", len(df['Controller'].unique()))
            
            # --- MAIN DATA TABLE ---
            st.subheader("📊 Production Integrity Matrix")
            gb = GridOptionsBuilder.from_dataframe(matrix)
            gb.configure_default_column(resizable=True, filterable=True, sortable=True)
            gb.configure_side_bar() # Adds a sidebar to the table for better filtering
            
            AgGrid(matrix, gridOptions=gb.build(), height=500, theme='alpine', enable_enterprise_modules=False)

            # --- GAP ANALYSIS ---
            st.subheader("🚨 Detected Gaps")
            missing_data = matrix[matrix.isnull().any(axis=1)]
            
            if not missing_data.empty:
                st.error(f"Alert: {len(missing_data)} VINs have missing torque data at one or more stations.")
                st.dataframe(missing_data.style.highlight_null(null_color='#ff4b4b'))
                
                # Combined Download
                csv_gaps = missing_data.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Gap Report", csv_gaps, "traceability_gaps.csv", "text/csv")
            else:
                st.success("Perfect Integrity! All VINs accounted for across all selected lines.")
                
            # Full Data Download
            csv_full = matrix.to_csv(index=False).encode('utf-8')
            st.download_button("📂 Download Full Matrix", csv_full, "full_traceability.csv", "text/csv")
        else:
            st.error("Connection Failed. Are you on the Proton Intranet? (Target: 10.200.28.208)")

st.sidebar.markdown("---")
st.sidebar.caption("System developed for industrial data tracking and VIN traceability automation.")
