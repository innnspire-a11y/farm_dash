import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import requests
from datetime import datetime, timedelta
import pytz
import altair as alt
import json
import math

# --- 1. SECURITY CHECK ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
    if "password_correct" not in st.session_state:
        st.text_input("FarmOS Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("FarmOS Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    return True

if not check_password():
    st.stop()

# --- 2. CONFIGURATION & STYLING ---
st.set_page_config(page_title="FarmOS Pro", layout="wide", page_icon="🚜")

st.markdown("""
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        [data-testid="stAppViewContainer"] { background-color: #0f172a; }
        [data-testid="stHeader"] { background: rgba(0,0,0,0); }
        .block-container { padding: 0rem; }
        [data-testid="stSidebar"] { background-color: #1e293b; border-right: 1px solid #334155; }
        .stDataFrame { background-color: #1e293b; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CROP KNOWLEDGE BASE (Stages + Care) ---
CROP_STAGES = {
    "Sweet Corn": {
        "totalDuration": 85,
        "stages": [
            {"name": "Emergence", "days": 10, "icon": "🌱", "care": ["Protect from birds", "Keep soil surface moist"]},
            {"name": "Vegetative", "days": 35, "icon": "🌿", "care": ["High nitrogen fertilizer", "Check for stalk borers"]},
            {"name": "Tasseling", "days": 20, "icon": "🌽", "care": ["Critical water stage", "Ensure pollination humidity"]},
            {"name": "Ripening", "days": 20, "icon": "✨", "care": ["Check kernel milkiness", "Prepare for harvest"]}
        ]
    },
    "Beetroot": {
        "totalDuration": 60,
        "stages": [
            {"name": "Germination", "days": 10, "icon": "🌱", "care": ["Thin seedlings to 5cm", "Consistent moisture"]},
            {"name": "Leaf Growth", "days": 25, "icon": "🍃", "care": ["Nitrogen liquid feed", "Keep weed-free"]},
            {"name": "Bulbing", "days": 25, "icon": "🟣", "care": ["Deep watering twice weekly", "Avoid high nitrogen now"]}
        ]
    },
    "Cabbages": {
        "totalDuration": 90,
        "stages": [
            {"name": "Establishment", "days": 20, "icon": "🌱", "care": ["Damping-off prevention", "Cutworm check"]},
            {"name": "Cupping", "days": 35, "icon": "🥬", "care": ["Regular irrigation", "Caterpillar monitoring"]},
            {"name": "Heading", "days": 35, "icon": "🟢", "care": ["Maintain moisture to prevent splitting", "Final feed"]}
        ]
    },
    "Onions": {
        "totalDuration": 150,
        "stages": [
            {"name": "Vegetative", "days": 50, "icon": "🌱", "care": ["Weed control is vital", "Nitrogen side-dressing"]},
            {"name": "Bulbing", "days": 70, "icon": "🧅", "care": ["Reduce water as leaves yellow", "Stop feeding"]},
            {"name": "Drying", "days": 30, "icon": "☀️", "care": ["Stop all irrigation", "Wait for neck collapse"]}
        ]
    }
}

# --- 4. CORE LOGIC FUNCTIONS ---
def get_sast_now():
    sast = datetime.now(pytz.timezone("Africa/Johannesburg"))
    return sast - timedelta(hours=2)

def calculate_polygon_area(coords):
    """Calculates area in square metres using the Shoelace formula and Earth radius."""
    if not coords or len(coords) < 3:
        return 0
    area = 0.0
    R = 6378137 # Earth's radius in metres
    for i in range(len(coords)):
        p1 = coords[i]
        p2 = coords[(i + 1) % len(coords)]
        area += math.radians(p2[0] - p1[0]) * (2 + math.sin(math.radians(p1[1])) + math.sin(math.radians(p2[1])))
    return abs(area * R * R / 2.0)

def process_crops(data):
    now = get_sast_now().replace(tzinfo=None)
    processed = []
    for item in data:
        p_date = datetime.strptime(item['planted'], "%Y-%m-%d") if isinstance(item['planted'], str) else pd.to_datetime(item['planted'])
        config = CROP_STAGES.get(item['name'], {"totalDuration": 90, "stages": []})
        total_days = config['totalDuration']
        ready_date = p_date + timedelta(days=total_days)
        days_passed = (now - p_date).days
        
        # Determine specific growth stage
        curr_stage = "Ready"
        curr_icon = "✅"
        stage_care = ["Harvest and cure."]
        accumulated = 0
        for s in config.get('stages', []):
            if accumulated <= days_passed < (accumulated + s['days']):
                curr_stage = s['name']
                curr_icon = s['icon']
                stage_care = s['care']
                break
            accumulated += s['days']

        days_left = (ready_date - now).days
        is_harvested = days_left < 0
        progress = 100 if is_harvested else max(0, min(100, int((days_passed / total_days) * 100)))

        processed.append({
            **item,
            "planted_str": p_date.strftime("%Y-%m-%d"),
            "progress": progress,
            "status": "Harvested" if is_harvested else f"{curr_icon} {curr_stage}",
            "days_left": days_left,
            "overdue_label": f"Overdue by {abs(days_left)}" if is_harvested else f"{days_left} days left",
            "is_harvested": is_harvested,
            "care_steps": stage_care
        })
    return processed

# --- 5. SIDEBAR & NAVIGATION ---
if 'crop_db' not in st.session_state:
    st.session_state.crop_db = [
        {"name": "Sweet Corn", "planted": "2025-11-15", "qty": "600 seedlings", "area": "4150 m²", "rainfall_mm": 45},
        {"name": "Beetroot", "planted": "2025-11-30", "qty": "200 seedlings", "area": "420 m²", "rainfall_mm": 12},
    ]

with st.sidebar:
    st.markdown("<h1 class='text-white text-2xl font-black'>🚜 FarmOS Pro</h1>", unsafe_allow_html=True)
    page = st.radio("Navigation:", ["📊 Dashboard", "🛰️ Field Mapper", "🌦️ Weather", "⚙️ Manage Inventory"])
    
    st.divider()
    if page == "📊 Dashboard":
        st.subheader("🗓️ Target Harvest Planner")
        target_date = st.date_input("Target Harvest Date:", value=datetime.now() + timedelta(days=90))
        calc = [{"Crop": k, "Plant By": (target_date - timedelta(days=v['totalDuration'])).strftime('%Y-%m-%d')} 
                for k, v in CROP_STAGES.items()]
        st.table(pd.DataFrame(calc))
    
    if st.button("Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

# --- 6. PAGE CONTENT ---

if page == "📊 Dashboard":
    processed_data = process_crops(st.session_state.crop_db)
    active = len([c for c in processed_data if not c['is_harvested']])
    crops_json = json.dumps(processed_data)
    
    # JavaScript + HTML Component for the Interactive Cards
    dashboard_html = f"""
    <script src="https://cdn.tailwindcss.com"></script>
    <div class="bg-[#0f172a] text-white p-8 font-sans min-h-screen">
        <h1 class="text-4xl font-extrabold tracking-tight">Farm Intelligence 🚜</h1>
        <p class="text-[#84cc16] font-mono font-bold mt-2 text-lg mb-10">{get_sast_now().strftime('%A, %B %d')}</p>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
            <div class="bg-[#1e293b] p-6 rounded-2xl border border-gray-800 shadow-xl">
                <p class="text-gray-400 text-sm font-semibold uppercase tracking-wider">Active Growing</p>
                <h2 class="text-4xl font-black mt-2 text-blue-500">{active}</h2>
            </div>
            <div class="bg-[#1e293b] p-6 rounded-2xl border border-gray-800 shadow-xl">
                <p class="text-gray-400 text-sm font-semibold uppercase tracking-wider">Harvested</p>
                <h2 class="text-4xl font-black mt-2 text-green-500">{len(processed_data)-active}</h2>
            </div>
        </div>

        <div id="card-container" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8"></div>

        <div id="modal-overlay" class="hidden fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div id="modal" class="bg-[#1e293b] w-full max-w-md rounded-3xl border border-slate-700 shadow-2xl p-8 transform transition-all">
                <h2 id="modal-title" class="text-3xl font-black mb-2"></h2>
                <p id="modal-status" class="text-lime-500 font-bold mb-6"></p>
                <div class="space-y-4" id="modal-steps"></div>
                <button onclick="closeModal()" class="w-full mt-8 bg-lime-600 hover:bg-lime-500 text-white font-bold py-4 rounded-xl transition">Dismiss</button>
            </div>
        </div>
    </div>

    <script>
        const data = {crops_json};
        
        function openModal(index) {{
            const crop = data[index];
            document.getElementById('modal-title').innerText = crop.name;
            document.getElementById('modal-status').innerText = "Current Stage: " + crop.status;
            const stepsCont = document.getElementById('modal-steps');
            stepsCont.innerHTML = crop.care_steps.map(step => 
                `<div class="flex items-center space-x-3 bg-slate-800/50 p-4 rounded-xl">
                    <span class="text-lime-500">✔</span>
                    <span class="text-sm text-slate-200">${{step}}</span>
                </div>`
            ).join('');
            
            document.getElementById('modal-overlay').classList.remove('hidden');
        }}

        function closeModal() {{
            document.getElementById('modal-overlay').classList.add('hidden');
        }}

        const container = document.getElementById('card-container');
        container.innerHTML = data.map((crop, i) => {{
            const ringColor = crop.is_harvested ? "#22c55e" : "#84cc16";
            const offset = 213.6 * (1 - crop.progress / 100);
            
            return `
            <div onclick="openModal(${{i}})" class="bg-[#1e293b] p-6 rounded-3xl border border-gray-800 shadow-lg cursor-pointer hover:border-lime-500/50 transition-all">
                <div class="flex justify-between items-start mb-6">
                    <h3 class="text-2xl font-bold text-white">${{crop.name}}</h3>
                    <span class="bg-slate-700 text-[10px] px-3 py-1 rounded-full font-bold uppercase tracking-widest text-slate-300">${{crop.status}}</span>
                </div>
                <div class="flex items-center space-x-5 mb-8">
                    <div class="relative w-20 h-20 flex items-center justify-center">
                        <svg class="w-full h-full transform -rotate-90">
                            <circle cx="40" cy="40" r="34" stroke="#2d3748" stroke-width="6" fill="transparent" />
                            <circle cx="40" cy="40" r="34" stroke="${{ringColor}}" stroke-width="6" fill="transparent" 
                                stroke-dasharray="213.6" stroke-dashoffset="${{offset}}" stroke-linecap="round" />
                        </svg>
                        <div class="absolute inset-0 flex items-center justify-center font-bold text-white text-sm">
                            ${{crop.is_harvested ? '✓' : crop.progress + '%'}}
                        </div>
                    </div>
                    <div>
                        <p class="text-xl font-black text-white">${{crop.overdue_label}}</p>
                        <p class="text-[11px] text-gray-500 mt-1">Planted: ${{crop.planted_str}}</p>
                        <p class="text-[11px] text-blue-400 font-bold">💧 Rain: ${{crop.rainfall_mm}}mm</p>
                    </div>
                </div>
                <div class="pt-5 border-t border-gray-800 flex justify-between">
                    <p class="text-xs font-bold text-lime-500">Area: <span class="text-white font-normal">${{crop.area}}</span></p>
                    <p class="text-xs font-bold text-lime-500">Qty: <span class="text-white font-normal">${{crop.qty}}</span></p>
                </div>
            </div>`;
        }}).join('');
    </script>
    """
    components.html(dashboard_html, height=1200, scrolling=True)

elif page == "🛰️ Field Mapper":
    st.markdown("<div class='p-8'><h1 class='text-white text-4xl font-black mb-4'>🛰️ Field Mapper</h1>", unsafe_allow_html=True)
    col1, col2 = st.columns([3, 1])
    
    # Initialize area variable
    calculated_area_m2 = 0
    
    with col1:
        m = folium.Map(location=[-22.86, 30.60], zoom_start=15, tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google Satellite")
        Draw(export=True).add_to(m)
        output = st_folium(m, width="100%", height=600)
        
        # Area Logic Integration
        if output.get("all_drawings"):
            last_drawing = output["all_drawings"][-1]
            if last_drawing["geometry"]["type"] == "Polygon":
                coords = last_drawing["geometry"]["coordinates"][0]
                calculated_area_m2 = calculate_polygon_area(coords)
    
    with col2:
        st.subheader("Link to Inventory")
        if output.get("all_drawings"):
            st.metric("Detected Area", f"{int(calculated_area_m2)} m²")
            with st.form("map_to_db"):
                selected_crop = st.selectbox("Assign shape to Crop:", list(CROP_STAGES.keys()))
                plant_date = st.date_input("Planting Date:", value=datetime.now())
                qty_input = st.text_input("Quantity:", value="100 seedlings")
                rain_input = st.number_input("Current Rainfall (mm):", min_value=0, value=0)
                if st.form_submit_button("✅ Save to Inventory"):
                    new_entry = {
                        "name": selected_crop, 
                        "planted": plant_date.strftime("%Y-%m-%d"), 
                        "qty": qty_input, 
                        "area": f"{int(calculated_area_m2)} m²", # UPDATED: Dynamic area injected here
                        "rainfall_mm": rain_input
                    }
                    st.session_state.crop_db.append(new_entry)
                    st.success(f"Added to Inventory with {int(calculated_area_m2)} m²!")
                    st.rerun()
        else:
            st.info("Draw a polygon on the map to calculate area and link to inventory.")

elif page == "🌦️ Weather":
    st.markdown("<div class='p-8'><h1 class='text-white text-4xl font-black mb-6'>🌦️ Local Weather</h1>", unsafe_allow_html=True)
    city = st.text_input("Enter Nearest Town:", "Sibasa")
    try:
        res = requests.get(f"https://wttr.in/{city}?format=j1").json()
        curr = res['current_condition'][0]
        st.metric("Temperature", f"{curr['temp_C']}°C", curr['weatherDesc'][0]['value'])
        
        # Rainfall History Chart
        st.subheader("📊 Crop Rainfall History")
        rain_df = pd.DataFrame(st.session_state.crop_db)
        if not rain_df.empty:
            chart = alt.Chart(rain_df).mark_bar(cornerRadiusTopLeft=10, cornerRadiusTopRight=10).encode(
                x='name:N', y='rainfall_mm:Q', color=alt.value('#2563eb'), tooltip=['name', 'rainfall_mm']
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)
    except:
        st.error("Weather service sync failed.")

elif page == "⚙️ Manage Inventory":
    st.markdown("<div class='p-8'>", unsafe_allow_html=True)
    st.title("⚙️ Manage Inventory")
    df_to_edit = pd.DataFrame(st.session_state.crop_db)
    df_to_edit["planted"] = pd.to_datetime(df_to_edit["planted"])
    
    edited_df = st.data_editor(df_to_edit, num_rows="dynamic", use_container_width=True,
        column_config={
            "name": st.column_config.SelectboxColumn("Crop", options=list(CROP_STAGES.keys())),
            "planted": st.column_config.DateColumn("Plant Date")
        }
    )
    
    if st.button("💾 Save All Changes", type="primary"):
        save_df = edited_df.copy()
        save_df["planted"] = save_df["planted"].dt.strftime('%Y-%m-%d')
        st.session_state.crop_db = save_df.to_dict('records')
        st.success("Database updated!")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
