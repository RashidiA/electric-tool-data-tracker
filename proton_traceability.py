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
    options.add_argument("--mute-audio") # Avoids libasound issues
    
    if os.path.exists("/usr/bin/chromium"):
        options.binary_location = "/usr/bin/chromium"
    elif os.path.exists("/usr/bin/chromium-browser"):
        options.binary_location = "/usr/bin/chromium-browser"
        
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
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
        status_text.text(f"🚀 Scanning {line_name} Line...")
        try:
            driver.get(url)
            time.sleep(12) # Increased wait for 36k+ results
            rows = driver.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                cells = row.find_elements(By.CLASS_NAME, "text-start")
                if len(cells) >= 6:
                    all_data.append({
                        "Line": line_name,
                        "Controller": cells[2].text.strip(),
                        "VIN": cells[5].text.strip(),
                        "Status": cells[0].text.strip()
                    })
        except Exception as e:
            st.error(f"Error on {line_name}: {e}")
        bar.progress((i + 1) / len(selected_lines))
    
    driver.quit()
    return pd.DataFrame(all_data)

st.title("🛡️ Proton Global Traceability Matrix")

selected_lines = st.multiselect("Select Lines to Audit:", options=list(LINE_URLS.keys()), default=["Trim", "Final"])

if st.button("Run Global Cross-Check"):
    if not selected_lines:
        st.warning("Please select at least one line.")
    else:
        df = scrape_line_data(selected_lines)
        if not df.empty:
            matrix = df.pivot_table(index='VIN', columns=['Line', 'Controller'], values='Status', aggfunc='first').reset_index()
            st.subheader("📊 Production Integrity Matrix")
            gb = GridOptionsBuilder.from_dataframe(matrix)
            gb.configure_default_column(resizable=True, filterable=True, sortable=True)
            AgGrid(matrix, gridOptions=gb.build(), height=500, theme='alpine')

            st.subheader("🚨 Detected Gaps")
            missing_data = matrix[matrix.isnull().any(axis=1)]
            if not missing_data.empty:
                st.error(f"Missing data for {len(missing_data)} VINs.")
                st.dataframe(missing_data.style.highlight_null(null_color='#ff4b4b'))
                st.download_button("📥 Download Gap Report", missing_data.to_csv(index=False).encode('utf-8'), "gaps.csv")
            else:
                st.success("All VINs clear!")
        else:
            st.error("No data found. Check VPN/Intranet connection to 10.200.28.208.")
