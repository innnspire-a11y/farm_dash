import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import requests
from datetime import datetime, timedelta
import pytz

# --- 1. SECURITY CHECK ---
def check_password():
    """Returns True if the user had the correct password."""
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input("FarmOS Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input + error.
        st.text_input("FarmOS Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct.
        return True

if not check_password():
    st.stop()  # Do not run the rest of the app if password isn't correct

# --- 2. CONFIGURATION ---
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

# --- 3. INITIAL DATA & STATE ---
if 'crop_db' not in st.session_state:
    st.session_state.crop_db = [
        {"name": "Sweet Corn", "planted": "2025-11-15", "qty": "600 seedlings", "area": "4150 m²"},
        {"name": "Beetroot", "planted": "2025-11-30", "qty": "200 seedlings", "area": "420 m²"},
        {"name": "Cabbages", "planted": "2025-08-05", "qty": "500 heads", "area": "1200 m²"},
        {"name": "Onions", "planted": "2025-06-28", "qty": "15 kg", "area": "3238 m²"},
    ]

CROP_STAGES = {
    "Beetroot": {"totalDuration": 60},
    "Sweet Corn": {"totalDuration": 85},
    "Cabbages": {"totalDuration": 90},
    "Onions": {"totalDuration": 150},
    "Okra": {"totalDuration": 65}
}

# --- 4. CORE LOGIC FUNCTIONS ---

def get_sast_now():
    return datetime.now(pytz.timezone("Africa/Johannesburg"))

def process_and_sort_crops(data):
    now = get_sast_now().replace(tzinfo=None)
    processed = []
    for item in data:
        try:
            p_date = datetime.strptime(item['planted'], "%Y-%m-%d") if isinstance(item['planted'], str) else pd.to_datetime(item['planted'])
        except:
            p_date = now
        
        duration = CROP_STAGES.get(item['name'], {"totalDuration": 90})['totalDuration']
        ready_date = p_date + timedelta(days=duration)
        days_left = (ready_date - now).days
        is_harvested = days_left < 0
        progress = 100 if is_harvested else max(0, int(((duration - days_left) / duration) * 100))
        
        processed.append({
            **item,
            "planted_str": p_date.strftime("%Y-%m-%d"),
            "ready_date": ready_date,
            "progress": progress,
            "status": "Harvested" if is_harvested else "Growing",
            "overdue_label": f"Overdue by {abs(days_left)}" if is_harvested else f"{days_left} days left",
            "is_harvested": is_harvested
        })
    processed.sort(key=lambda x: (x['is_harvested'], x['ready_date'] if not x['is_harvested'] else -x['ready_date'].timestamp()))
    return processed

# --- 5. NAVIGATION & SIDEBAR ---

with st.sidebar:
    st.markdown("<h1 class='text-white text-2xl font-black'>🚜 FarmOS Pro</h1>", unsafe_allow_html=True)
    page = st.radio("Navigation:", ["📊 Dashboard", "🛰️ Field Mapper", "🌦️ Weather", "⚙️ Manage Inventory"])
    
    st.divider()
    if page == "⚙️ Manage Inventory":
        st.subheader("Edit Records")
        df_to_edit = pd.DataFrame(st.session_state.crop_db)
        df_to_edit["planted"] = pd.to_datetime(df_to_edit["planted"])
        edited_df = st.data_editor(df_to_edit, num_rows="dynamic", hide_index=True, use_container_width=True,
            column_config={
                "name": st.column_config.SelectboxColumn("Crop", options=list(CROP_STAGES.keys())),
                "planted": st.column_config.DateColumn("Plant Date")
            })
        if st.button("💾 Update Database"):
            save_df = edited_df.copy()
            save_df["planted"] = save_df["planted"].dt.strftime('%Y-%m-%d')
            st.session_state.crop_db = save_df.to_dict('records')
            st.rerun()

    elif page == "📊 Dashboard":
        st.subheader("🗓️ Target Harvest Planner")
        target_date = st.date_input("When do you want to harvest?", value=datetime.now() + timedelta(days=90))
        if target_date:
            calc = [{"Crop": k, "Plant By": (target_date - timedelta(days=v['totalDuration'])).strftime('%Y-%m-%d')} 
                    for k, v in CROP_STAGES.items()]
            st.table(pd.DataFrame(calc))
    
    if st.button("Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

# --- 6. PAGE CONTENT RENDERING ---

if page == "📊 Dashboard":
    processed_data = process_and_sort_crops(st.session_state.crop_db)
    now_str = get_sast_now().strftime('%A, %B %d, %Y')
    active = len([c for c in processed_data if not c['is_harvested']])
    
    cards_html = ""
    for crop in processed_data:
        ring_color = "#22c55e" if crop['is_harvested'] else "#84cc16"
        cards_html += f"""
        <div class="bg-[#1e293b] p-6 rounded-3xl border border-gray-800 shadow-lg">
            <div class="flex justify-between items-start mb-6">
                <h3 class="text-2xl font-bold text-white">{crop['name']}</h3>
                <span class="bg-gray-700 text-[10px] px-3 py-1 rounded-full font-bold uppercase tracking-widest text-slate-300">{crop['status']}</span>
            </div>
            <div class="flex items-center space-x-5 mb-8">
                <div class="relative w-20 h-20 flex items-center justify-center">
                    <svg class="w-full h-full transform -rotate-90">
                        <circle cx="40" cy="40" r="34" stroke="#2d3748" stroke-width="6" fill="transparent" />
                        <circle cx="40" cy="40" r="34" stroke="{ring_color}" stroke-width="6" fill="transparent" 
                            stroke-dasharray="213.6" stroke-dashoffset="{213.6 * (1 - crop['progress']/100)}" stroke-linecap="round" />
                    </svg>
                    <div class="absolute inset-0 flex items-center justify-center font-bold text-white text-sm">
                        { '✓' if crop['is_harvested'] else str(crop['progress']) + '%' }
                    </div>
                </div>
                <div>
                    <p class="text-xl font-black text-white">{crop['overdue_label']}</p>
                    <p class="text-[11px] text-gray-500 mt-1">Planted: {crop['planted_str']}</p>
                </div>
            </div>
            <div class="pt-5 border-t border-gray-800 flex justify-between">
                <p class="text-xs font-bold text-lime-500">Area: <span class="text-white font-normal">{crop.get('area', 'N/A')}</span></p>
                <p class="text-xs font-bold text-lime-500">Qty: <span class="text-white font-normal">{crop.get('qty', 'N/A')}</span></p>
            </div>
        </div>
        """

    full_html = f"""
    <script src="https://cdn.tailwindcss.com"></script>
    <div class="bg-[#0f172a] text-white p-8 font-sans min-h-screen">
        <h1 class="text-4xl font-extrabold tracking-tight">Farm Progress Dashboard 🚜</h1>
        <p class="text-[#84cc16] font-mono font-bold mt-2 text-lg mb-10">{now_str}</p>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
            <div class="bg-[#1e293b] p-6 rounded-2xl border border-gray-800 shadow-xl">
                <p class="text-gray-400 text-sm font-semibold uppercase tracking-wider">Active Growing</p>
                <h2 class="text-4xl font-black mt-2 text-blue-500">{active}</h2>
            </div>
            <div class="bg-[#1e293b] p-6 rounded-2xl border border-gray-800 shadow-xl">
                <p class="text-gray-400 text-sm font-semibold uppercase tracking-wider">Harvested</p>
                <h2 class="text-4xl font-black mt-2 text-green-500">{len(processed_data)-active}</h2>
            </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">{cards_html}</div>
    </div>
    """
    components.html(full_html, height=1200, scrolling=True)

elif page == "🛰️ Field Mapper":
    st.markdown("<div class='p-8'><h1 class='text-white text-4xl font-black mb-4'>🛰️ Field Mapper</h1>", unsafe_allow_html=True)
    st.write("Draw polygons to define crop portions. Coordinates are captured below.")
    m = folium.Map(location=[-23.9, 29.4], zoom_start=15, tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google Satellite")
    Draw(export=True).add_to(m)
    output = st_folium(m, width="100%", height=600)
    if output.get("all_drawings"):
        st.json(output["all_drawings"])
    st.markdown("</div>", unsafe_allow_html=True)

elif page == "🌦️ Weather":
    st.markdown("<div class='p-8'><h1 class='text-white text-4xl font-black mb-6'>🌦️ Local Weather</h1>", unsafe_allow_html=True)
    city = st.text_input("Enter Nearest Town:", "Polokwane")
    try:
        res = requests.get(f"https://wttr.in/{city}?format=j1").json()
        curr = res['current_condition'][0]
        w_html = f"""
        <script src="https://cdn.tailwindcss.com"></script>
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <div class="bg-blue-600 p-6 rounded-2xl text-white"><p class="text-xs uppercase">Temp</p><h1 class="text-4xl font-black">{curr['temp_C']}°C</h1></div>
            <div class="bg-slate-800 p-6 rounded-2xl text-white"><p class="text-xs uppercase">Humidity</p><h1 class="text-4xl font-black">{curr['humidity']}%</h1></div>
            <div class="bg-slate-800 p-6 rounded-2xl text-white"><p class="text-xs uppercase">Wind</p><h1 class="text-4xl font-black">{curr['windspeedKmph']}km/h</h1></div>
            <div class="bg-slate-800 p-6 rounded-2xl text-white"><p class="text-xs uppercase">Condition</p><h1 class="text-2xl font-black">{curr['weatherDesc'][0]['value']}</h1></div>
        </div>
        """
        components.html(w_html, height=150)
        st.subheader("7-Day Agricultural Forecast")
        forecast = [{"Date": d['date'], "Max": f"{d['maxtempC']}°C", "Min": f"{d['mintempC']}°C", "Rain": f"{d['hourly'][0]['chanceofrain']}%"} for d in res['weather']]
        st.table(pd.DataFrame(forecast))
    except:
        st.warning("Weather service currently unavailable.")
    st.markdown("</div>", unsafe_allow_html=True)