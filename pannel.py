# panel.py - 最終完整版（全中英並列 + 地圖即時切換生效 + 性能優化 + 關鍵修正）
# 修正內容：
# 1. 解決「Central & Western」選取時所有數據為 0 的問題 → 加入 district 名稱標準化 mapping
# 2. 取消所有抽樣（private buildings 與 HeatMap 皆載入完整數據）
# 3. 新增：距離與覆蓋率比例圖表（在私樓分析下方顯示折線圖）
# 4. 新增：禁止滑鼠滾輪對 Folium 地圖及所有 Streamlit 圖表的影響
# 作者：THZH Program - Zhou Ziyue
# 運行指令: streamlit run panel.py

import streamlit as st
import pandas as pd
import numpy as np
from streamlit_folium import folium_static
import folium
from folium.plugins import FastMarkerCluster, HeatMap
import json
import geopandas as gpd
from scipy.spatial.distance import cdist
import re
import os

# ====================== 頁面配置 ======================
st.set_page_config(
    page_title="香港回收網絡優化 - Green Loop Challenge / HK Recycling Network Optimization",
    page_icon="♻️",
    layout="wide"
)

# ====================== 語言切換 ======================
with st.sidebar:
    lang = st.selectbox("語言 / Language", ["中文", "English"], index=0)

# ====================== 文字字典（所有地方中英並列） ======================
texts = {
    "中文": {
        "title": "♻️ 香港回收網絡優化 - Green Loop Challenge / HK Recycling Network Optimization",
        "loading": "正在載入資料... / Loading data...",
        "filters": "🔍 篩選條件（即時更新覆蓋率） / Filter Conditions (Live Update)",
        "district": "地區 / District",
        "waste_type": "回收類型 / Waste Type",
        "station_type": "回收點類型 / Station Type",
        "premium_only": "僅優質站點 / Premium Stations Only",
        "distance": "覆蓋距離 (米) / Coverage Distance (meters)",
        "show_public": "顯示公屋標記（紅色） / Show Public Estates Markers (Red)",
        "show_private_heat": "顯示私樓密度熱力圖 / Show Private Buildings Density Heatmap",
        "private_title": "選定地區覆蓋分析（含最近回收站資訊） / Selected District Coverage Analysis (with Nearest Station Info)",
        "covered_buildings": "符合條件的建築數 / Buildings Covered",
        "coverage_rate": "覆蓋率 / Coverage Rate",
        "of_total": "佔總數 / of Total",
        "premium_ratio": "最近為 Recycling Stations（優質站）比例 / Nearest are Recycling Stations (Premium)",
        "common_waste": "垃圾回收種類比例（選定地區） / Waste Type Proportions (Selected District)",
        "formula_title": "覆蓋率計算公式（選定地區） / Coverage Rate Formula (Selected District)",
        "recycling_points": "回收點 / Recycling Points",
        "public_coverage": "公屋覆蓋率 / Public Estates Coverage",
        "private_coverage": "私樓覆蓋率 / Private Buildings Coverage",
        "map_title": "全香港回收網絡地圖 / Hong Kong Recycling Network Map",
        "proposal": "數據驅動提案 / Data-Driven Proposal",
        "insight": "核心洞察 / Key Insight",
        "suggestion": "建議 / Recommendation",
        "impact": "預期影響 / Expected Impact",
        "no_data": "無符合條件資料 / No matching data",
        "distance_coverage_trend": "覆蓋率隨距離變化趨勢 / Coverage Rate vs. Distance Trend"
    },
    "English": {
        "title": "♻️ Hong Kong Recycling Network Optimization - Green Loop Challenge",
        "loading": "Loading data...",
        "filters": "🔍 Filter Conditions (Live Update)",
        "district": "District",
        "waste_type": "Waste Type",
        "station_type": "Station Type",
        "premium_only": "Premium Stations Only",
        "distance": "Coverage Distance (meters)",
        "show_public": "Show Public Estates Markers (Red)",
        "show_private_heat": "Show Private Buildings Density Heatmap",
        "private_title": "Selected District Coverage Analysis (with Nearest Station Info)",
        "covered_buildings": "Buildings Covered",
        "coverage_rate": "Coverage Rate",
        "of_total": "of Total",
        "premium_ratio": "Nearest are Recycling Stations (Premium)",
        "common_waste": "Waste Type Proportions (Selected District)",
        "formula_title": "Coverage Rate Formula (Selected District)",
        "recycling_points": "Recycling Points",
        "public_coverage": "Public Estates Coverage",
        "private_coverage": "Private Buildings Coverage",
        "map_title": "Hong Kong Recycling Network Map",
        "proposal": "Data-Driven Proposal",
        "insight": "Key Insight",
        "suggestion": "Recommendation",
        "impact": "Expected Impact",
        "no_data": "No matching data",
        "distance_coverage_trend": "Coverage Rate vs. Distance Trend"
    }
}
t = texts[lang]

# ====================== 新增：禁用滑鼠滾輪對 Streamlit 所有圖表的影響（CSS + JS 注入） ======================
st.markdown("""
    <style>
        /* 禁止整個頁面不必要的滾輪縮放（但允許頁面正常滾動） */
        .stApp {
            overflow-x: hidden;
        }
        /* 針對 Streamlit 原生圖表容器，阻止滾輪事件冒泡 */
        .stPlotlyChart, .element-container [data-testid="stPlotlyChart"], 
        [data-testid="stDeckGlJsonChart"], [kind="line_chart"], [kind="bar_chart"] {
            pointer-events: auto !important;
        }
    </style>

    <script>
        // 頁面載入後，阻止所有圖表元素的 wheel 事件（zoom/scroll）
        document.addEventListener('DOMContentLoaded', function() {
            // 針對 Folium iframe（streamlit-folium 產生的）
            const iframes = document.querySelectorAll('iframe[src*="folium"]');
            iframes.forEach(iframe => {
                iframe.addEventListener('wheel', function(e) {
                    e.stopPropagation();
                    e.preventDefault();
                }, { passive: false });
            });

            // 針對 Streamlit 原生圖表（line_chart, bar_chart 等）
            const charts = document.querySelectorAll('[data-testid="stPlotlyChart"], .stPlotlyChart, [kind="line_chart"], [kind="bar_chart"]');
            charts.forEach(chart => {
                chart.addEventListener('wheel', function(e) {
                    e.stopPropagation();
                    e.preventDefault();
                }, { passive: false });
            });

            // 持續監聽動態新增的圖表元素
            const observer = new MutationObserver(() => {
                const newCharts = document.querySelectorAll('[data-testid="stPlotlyChart"], .stPlotlyChart');
                newCharts.forEach(chart => {
                    if (!chart.dataset.wheelDisabled) {
                        chart.addEventListener('wheel', function(e) {
                            e.stopPropagation();
                            e.preventDefault();
                        }, { passive: false });
                        chart.dataset.wheelDisabled = 'true';
                    }
                });
            });
            observer.observe(document.body, { childList: true, subtree: true });
        });
    </script>
""", unsafe_allow_html=True)

# ====================== 地區名稱標準化（解決 Central & Western 為 0 的核心問題） ======================
def normalize_district_name(district):
    if pd.isna(district) or str(district).strip() == "":
        return "Unknown"
    d = str(district).strip().replace("_", " ").replace("And", "&").replace(" and ", " & ")
    mapping = {
        "Central Western": "Central & Western",
        "Central and Western": "Central & Western",
        "Central_Western": "Central & Western",
        "Kwai Tsing": "Kwai Tsing",
        "Yau Tsim Mong": "Yau Tsim Mong",
        "Kwun Tong": "Kwun Tong",
        "Yuen Long": "Yuen Long",
        "Tuen Mun": "Tuen Mun",
        "Sai Kung": "Sai Kung",
        "Sha Tin": "Sha Tin",
        "Tai Po": "Tai Po",
        "North": "North",
        "Islands": "Islands",
        "Eastern": "Eastern",
        "Southern": "Southern",
        "Wan Chai": "Wan Chai",
        "Sham Shui Po": "Sham Shui Po",
        "Kowloon City": "Kowloon City",
        "Wong Tai Sin": "Wong Tai Sin",
        "Tsuen Wan": "Tsuen Wan"
    }
    return mapping.get(d, d)

# ====================== 數據加載 ======================
@st.cache_data
def load_recycling_points():
    try:
        df = pd.read_csv("Recyclable-Collection-Points-Data.csv", encoding='utf-8')
        df.columns = df.columns.str.strip()
        mapping = {'cp_id': 'id', 'cp_state': 'status', 'district_id': 'district',
                   'address_en': 'address_en', 'address_tc': 'address_tc',
                   'lat': 'latitude', 'lgt': 'longitude', 'waste_type': 'waste_types',
                   'legend': 'type', 'openhour_tc': 'hours_tc'}
        df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
        df = df.dropna(subset=['latitude', 'longitude'])
        df = df[(df['latitude'] != 0) & (df['longitude'] != 0)]
        df = df[(df['latitude'].between(22.15, 22.55)) & (df['longitude'].between(113.8, 114.4))]
        df['waste_types'] = df['waste_types'].fillna('Unknown')
        df['type'] = df.get('type', '回收站').fillna('回收站')
        df['district'] = df.get('district', 'Unknown').fillna('Unknown')
        df['is_premium'] = df['type'].str.contains('GREEN@COMMUNITY|Recycling Station|Recycling Store', case=False, na=False)
        
        df['district'] = df['district'].apply(normalize_district_name)
        return df
    except Exception as e:
        st.error(f"回收點 CSV 加載失敗 / Recycling Points CSV Load Failed: {e}")
        return pd.DataFrame()

@st.cache_data
def load_public_housing():
    path = "prh-estates.json"
    if not os.path.exists(path): return pd.DataFrame()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        estates = []
        for item in data if isinstance(data, list) else [data]:
            estate_name = item.get("Estate Name", {}).get("en", "Unknown")
            district = item.get("District Name", {}).get("en", "Unknown")
            lat = item.get("Estate Map Latitude")
            lon = item.get("Estate Map Longitude")
            if lat is None or lon is None: continue
            flats = 0
            flats_str = str(item.get("No. of Units", item.get("No. of Rental Flats", "0")))
            match = re.search(r'\d[\d\s,]*', flats_str)
            if match: flats = int(match.group().replace(" ", "").replace(",", ""))
            estates.append({'estate_name': estate_name, 'district': district, 'flats': flats,
                            'latitude': lat, 'longitude': lon})
        df = pd.DataFrame(estates)
        df['district'] = df['district'].apply(normalize_district_name)
        return df
    except:
        return pd.DataFrame()

@st.cache_data
def load_private_buildings():
    path = "PrivateBuildings.csv"
    if not os.path.exists(path): 
        st.error(f"私宅文件不存在 / Private Buildings file not found: {path}")
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, usecols=['LATITUDE', 'LONGITUDE', 'SEARCH1_E'], 
                         low_memory=False, encoding='utf-8-sig', on_bad_lines='skip')
        df.columns = df.columns.str.strip()
        df = df.rename(columns={'SEARCH1_E': 'district', 'LATITUDE': 'latitude', 'LONGITUDE': 'longitude'})
        df = df.dropna(subset=['latitude', 'longitude'])
        df = df[(df['latitude'].between(22.0, 22.6)) & (df['longitude'].between(113.8, 114.5))]
        
        df['type'] = 'Private Building'
        df['district'] = df['district'].apply(normalize_district_name)
        return df[['latitude', 'longitude', 'district', 'type']]
    except Exception as e:
        st.error(f"私宅載入失敗 / Private buildings load failed: {str(e)}")
        return pd.DataFrame()

# ====================== 覆蓋率計算 ======================
def calculate_district_coverage(recycle_df, estate_df, distance_km=0.5):
    if recycle_df.empty or estate_df.empty:
        return {'coverage_rate': 0.0, 'covered': 0, 'total': 0}
    coords_rec = recycle_df[['latitude', 'longitude']].values
    coords_est = estate_df[['latitude', 'longitude']].values
    distances = cdist(coords_est, coords_rec) * 111
    min_dist = distances.min(axis=1)
    covered = min_dist <= distance_km
    return {
        'coverage_rate': covered.mean(),
        'covered': int(covered.sum()),
        'total': len(estate_df)
    }

def calculate_private_coverage(recycle_df, private_df, distance_km=0.5):
    if recycle_df.empty or private_df.empty:
        return {'coverage_rate': 0.0, 'covered': 0, 'total': 0,
                'nearest_premium_ratio': 0.0}
    coords_rec = recycle_df[['latitude', 'longitude']].values
    coords_priv = private_df[['latitude', 'longitude']].values
    distances = cdist(coords_priv, coords_rec) * 111
    min_dist = distances.min(axis=1)
    covered_mask = min_dist <= distance_km
    nearest_idx = distances.argmin(axis=1)
    nearest_premium_ratio = 0.0
    if covered_mask.any():
        nearest_df = recycle_df.iloc[nearest_idx[covered_mask]]
        nearest_premium_ratio = nearest_df['is_premium'].mean()
    return {
        'coverage_rate': covered_mask.mean(),
        'covered': int(covered_mask.sum()),
        'total': len(private_df),
        'nearest_premium_ratio': nearest_premium_ratio
    }

# ====================== 地圖生成函數（新增 scrollWheelZoom=False） ======================
def create_map(show_public, show_heat, filtered_recycle, filtered_public, filtered_private):
    m = folium.Map(
        location=[22.3, 114.1], 
        zoom_start=11, 
        tiles="CartoDB positron", 
        prefer_canvas=True,
        scrollWheelZoom=False,          # 禁止滑鼠滾輪縮放
        zoomControl=True,               # 仍保留 + - 按鈕
        dragging=True                   # 仍允許拖曳（可改成 False 如果完全不希望互動）
    )
    
    if not filtered_recycle.empty:
        locations = filtered_recycle[['latitude', 'longitude']].values.tolist()
        popups = [
            f"{row.get('address_tc', '回收點 / Point')}<br>"
            f"類型 / Type: {row['type']}<br>"
            f"垃圾種類 / Waste: {row.get('waste_types', 'Unknown')}"
            for _, row in filtered_recycle.iterrows()
        ]
        FastMarkerCluster(locations, popups=popups).add_to(m)
    
    if show_public and not filtered_public.empty:
        for _, row in filtered_public.iterrows():
            folium.Marker(
                [row['latitude'], row['longitude']],
                popup=f"{row['estate_name']}<br>單位 / Units: {row.get('flats', 0):,}",
                icon=folium.Icon(color='red', icon='home')
            ).add_to(m)
    
    if show_heat and not filtered_private.empty:
        heat_data = filtered_private[['latitude', 'longitude']]
        HeatMap(heat_data.values.tolist(),
                radius=15, blur=20, gradient={0.2:'yellow', 0.5:'orange', 0.8:'red'}).add_to(m)
    
    return m

# ====================== 主程序 ======================
def main():
    st.markdown(f'<h1 class="main-header">{t["title"]}</h1>', unsafe_allow_html=True)
    
    with st.spinner(t["loading"]):
        df_recycle = load_recycling_points()
        df_public = load_public_housing()
        df_private = load_private_buildings()
    
    if df_recycle.empty:
        st.error(t["no_data"])
        return
    
    with st.expander(t["filters"], expanded=True):
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            selected_district = st.selectbox(t["district"], ['全部 / All'] + sorted(df_recycle['district'].unique().tolist()))
        with col2:
            waste_options = ['全部 / All'] + sorted(set(t.strip() for types in df_recycle['waste_types'] if pd.notna(types) for t in str(types).split(',')))
            selected_waste = st.selectbox(t["waste_type"], waste_options)
        with col3:
            selected_type = st.selectbox(t["station_type"], ['全部 / All'] + sorted(df_recycle['type'].unique().tolist()))
        with col4:
            premium_only = st.checkbox(t["premium_only"], False)
        with col5:
            distance_m = st.slider(t["distance"], 100, 1000, 500, step=50)
            distance_km = distance_m / 1000.0
    
    filtered_recycle = df_recycle.copy()
    if selected_district != '全部 / All':
        filtered_recycle = filtered_recycle[filtered_recycle['district'] == selected_district]
    if selected_waste != '全部 / All':
        filtered_recycle = filtered_recycle[filtered_recycle['waste_types'].str.contains(selected_waste, na=False, case=False)]
    if selected_type != '全部 / All':
        filtered_recycle = filtered_recycle[filtered_recycle['type'] == selected_type]
    if premium_only:
        filtered_recycle = filtered_recycle[filtered_recycle['is_premium']]
    
    filtered_public = df_public[df_public['district'] == selected_district] if selected_district != '全部 / All' else df_public
    filtered_private = df_private[df_private['district'] == selected_district] if selected_district != '全部 / All' else df_private
    
    cov_pub = calculate_district_coverage(filtered_recycle, filtered_public, distance_km)
    cov_priv = calculate_private_coverage(filtered_recycle, filtered_private, distance_km)
    
    colA, colB, colC = st.columns(3)
    colA.metric(t["recycling_points"], f"{len(filtered_recycle):,}")
    colB.metric(t["public_coverage"], f"{cov_pub['coverage_rate']:.1%}")
    colC.metric(t["private_coverage"], f"{cov_priv['coverage_rate']:.1%}")
    
    st.markdown(f"## {t['private_title']}（{distance_m}米 / {distance_m} meters）", unsafe_allow_html=True)
    st.metric(
        label=t["covered_buildings"],
        value=f"{cov_priv['covered']:,} / {cov_priv['total']:,}",
        delta=f"{cov_priv['coverage_rate']:.1%} {t['coverage_rate']}"
    )
    st.metric(t["premium_ratio"], f"{cov_priv['nearest_premium_ratio']:.1%}")
    
    # ====================== 距離與覆蓋率比例圖表 ======================
    if not filtered_recycle.empty and (not filtered_public.empty or not filtered_private.empty):
        st.subheader(t["distance_coverage_trend"])
        
        distance_points = list(range(100, 1050, 50))
        public_coverages = []
        private_coverages = []
        
        for d_m in distance_points:
            d_km = d_m / 1000.0
            pub_cov = calculate_district_coverage(filtered_recycle, filtered_public, d_km)['coverage_rate'] * 100
            priv_cov = calculate_private_coverage(filtered_recycle, filtered_private, d_km)['coverage_rate'] * 100
            public_coverages.append(pub_cov)
            private_coverages.append(priv_cov)
        
        trend_df = pd.DataFrame({
            "距離 (米) / Distance (m)": distance_points,
            "公屋覆蓋率 (%) / Public Estates (%)": public_coverages,
            "私樓覆蓋率 (%) / Private Buildings (%)": private_coverages
        })
        
        st.line_chart(
            trend_df.set_index("距離 (米) / Distance (m)"),
            use_container_width=True,
            height=400
        )
        
        current_pub = cov_pub['coverage_rate'] * 100
        current_priv = cov_priv['coverage_rate'] * 100
        st.caption(f"目前 {distance_m} 米：公屋 {current_pub:.1f}% / 私樓 {current_priv:.1f}%")
    else:
        st.info("無足夠資料繪製距離-覆蓋率趨勢圖 / Not enough data to plot distance-coverage trend.")

    st.subheader(t["common_waste"])
    waste_series = filtered_recycle['waste_types']
    if not waste_series.empty:
        prop = waste_series.value_counts(normalize=True).head(8) * 100
        st.bar_chart(prop, use_container_width=True)
        for wtype, pct in prop.items():
            st.write(f"• **{wtype}**：{pct:.1f}% / **{wtype}**: {pct:.1f}%")
    else:
        st.write(t["no_data"])
    
    st.subheader(t["map_title"])
    
    show_public = st.checkbox(t["show_public"], value=False)
    show_heat = st.checkbox(t["show_private_heat"], value=True)
    
    m = create_map(show_public, show_heat, filtered_recycle, filtered_public, filtered_private)
    folium_static(m, width=1200, height=650)
    
    st.markdown("---")
if __name__ == '__main__':
    main()