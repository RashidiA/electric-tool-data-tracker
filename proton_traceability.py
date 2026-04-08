import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from streamlit_autorefresh import st_autorefresh
import time

st.set_page_config(page_title="Proton VIN Traceability", layout="wide")
st_autorefresh(interval=60000, key="datarefresh") # Refresh every 60 seconds

# Dictionary of all 70++ Controller Groups
DASHBOARDS = {
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

def scrape_all_dashboards():
    chrome_options = Options()
    chrome_options.add_argument("--headless") # Run without opening a window
    driver = webdriver.Chrome(options=chrome_options)
    
    all_data = []
    
    for section, url in DASHBOARDS.items():
        try:
            driver.get(url)
            time.sleep(3) # Wait for JS to load torque data
            html = driver.page_source
            tables = pd.read_html(html)
            if tables:
                df = tables[0]
                df['Section'] = section # Track which line the data came from
                all_data.append(df)
        except Exception as e:
            st.error(f"Error scraping {section}: {e}")
            
    driver.quit()
    return pd.concat(all_data, ignore_index=True) if all_data else None

st.title("🚗 Proton Production VIN Traceability Matrix")
st.info("Status: Live Monitoring (Auto-refresh 60s)")

raw_df = scrape_all_dashboards()

if raw_df is not None:
    # 1. Pivot the data to create the Matrix
    # We assume columns in dashboard are: 'VIN', 'Controller Name', 'Torque (Nm)'
    try:
        matrix = raw_df.pivot_table(index='VIN', 
                                    columns='Controller Name', 
                                    values='Torque (Nm)', 
                                    aggfunc='first')

        # 2. Visual Styling: Red for Missing (NaN)
        def style_missing(val):
            return 'background-color: #ffcccc' if pd.isna(val) else ''

        st.subheader("Data Matrix (Scroll Right for all 70+ Controllers)")
        st.dataframe(matrix.style.applymap(style_missing), use_container_width=True)

        # 3. Analytics: Find Missing VINs
        st.divider()
        st.subheader("⚠️ Missing Torque Data Summary")
        missing_mask = matrix.isna().any(axis=1)
        missing_vins = matrix[missing_mask]
        
        if not missing_vins.empty:
            st.warning(f"Found {len(missing_vins)} VINs with incomplete controller data.")
            st.write(missing_vins)
        else:
            st.success("All current VINs have complete torque data across all stations.")

    except KeyError as e:
        st.error(f"Column name mismatch. Found: {list(raw_df.columns)}. Expected 'VIN', 'Controller Name', 'Torque (Nm)'")
