import folium
from folium.plugins import HeatMap, MarkerCluster
import geopandas as gpd
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

# --- Page Setup ---
st.set_page_config(
    page_title="EV Charging Infrastructure Visualiser",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Raw GitHub Dataset URL ---
DEFAULT_GITHUB_URL = "https://raw.githubusercontent.com/amcbhome/spatial-data-cleaner/main/electric-vehicle-public-charging-devices.csv"

# --- Plain English Label Dictionary ---
LABEL_MAP = {
    "areacd": "Area Code",
    "ladcd": "Area Code",
    "gss_code": "Area Code",
    "area_code": "Area Code",
    "lad23cd": "Area Code",
    "areanm": "Local Authority Name",
    "ladnm": "Local Authority Name",
    "ladnmw": "Welsh Local Authority Name",
    "region": "Region / Nation",
    "period": "Year / Time Period",
    "value": "Total Charging Devices",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "lat": "Latitude",
    "lon": "Longitude",
}

# --- ONS Centroid Lookup Table ---
ONS_LA_CENTROIDS = {
    "W06000024": (51.7480, -3.3780),  # Merthyr Tydfil
    "E06000001": (54.6860, -1.2130),  # Hartlepool
    "E08000025": (52.4862, -1.8904),  # Birmingham
    "E08000035": (53.8008, -1.5491),  # Leeds
    "S12000033": (57.1497, -2.0943),  # Aberdeen City
    "E09000001": (51.5127, -0.0918),  # City of London
    "S12000034": (57.2832, -2.5714),  # Aberdeenshire
    "E07000223": (50.8351, -0.3180),  # Adur
    "E08000012": (53.4808, -2.2426),  # Manchester
    "E08000019": (53.4084, -2.9916),  # Liverpool
    "E08000010": (54.9783, -1.6178),  # Newcastle
    "S12000049": (55.9533, -3.1883),  # Edinburgh
    "W06000015": (51.6214, -3.9436),  # Swansea
}


def get_friendly_label(col_name: str) -> str:
    """Translates technical database headers to plain English labels."""
    col_lower = col_name.lower().strip()
    return LABEL_MAP.get(col_lower, col_name.replace("_", " ").title())


@st.cache_data
def load_dataset(url: str) -> pd.DataFrame:
    return pd.read_csv(url)


# --- Header & Intro ---
st.title("⚡ Public EV Charging Infrastructure Explorer")
st.caption(
    "Interactive spatial visualization of public electric vehicle charging infrastructure across the UK."
)

# --- Sidebar Visual Controls ---
st.sidebar.title("🎨 Visual Controls")

map_style = st.sidebar.selectbox(
    "Basemap Theme",
    ["CartoDB positron", "OpenStreetMap", "CartoDB dark_matter"],
    index=0,
    help="Switch between light, dark, and standard terrain basemaps.",
)

map_mode = st.sidebar.radio(
    "Spatial Overlay",
    ["Clustered Markers", "Density Heatmap"],
    index=0,
    help="Cluster individual device points or view regional device density.",
)

heatmap_radius = 15
if map_mode == "Density Heatmap":
    heatmap_radius = st.sidebar.slider(
        "Heatmap Point Radius", 5, 30, 15, help="Adjust visual density spread."
    )

st.sidebar.markdown("---")
color_theme = st.sidebar.selectbox(
    "Chart Palette",
    ["Blues", "Viridis", "Plasma", "Plotly3"],
    index=0,
    help="Color scheme for analytical charts.",
)

# --- Load & Parse Data ---
try:
    df_raw = load_dataset(DEFAULT_GITHUB_URL)

    cols_lower = {col.lower(): col for col in df_raw.columns}
    found_lat = next(
        (cols_lower[c] for c in ["latitude", "lat", "y"] if c in cols_lower), None
    )
    found_lon = next(
        (cols_lower[c] for c in ["longitude", "long", "lon", "x"] if c in cols_lower),
        None,
    )
    code_col = next(
        (
            cols_lower[c]
            for c in ["areacd", "ladcd", "area_code", "gss_code", "lad23cd"]
            if c in cols_lower
        ),
        None,
    )

    if found_lat and found_lon:
        df_raw[found_lat] = pd.to_numeric(df_raw[found_lat], errors="coerce")
        df_raw[found_lon] = pd.to_numeric(df_raw[found_lon], errors="coerce")
        df_raw = df_raw.dropna(subset=[found_lat, found_lon])
        gdf = gpd.GeoDataFrame(
            df_raw,
            geometry=gpd.points_from_xy(df_raw[found_lon], df_raw[found_lat]),
            crs="EPSG:4326",
        )
    elif code_col:
        df_raw["areacd_clean"] = df_raw[code_col].astype(str).str.upper()
        df_raw["latitude"] = df_raw["areacd_clean"].map(
            lambda x: ONS_LA_CENTROIDS[x][0] if x in ONS_LA_CENTROIDS else 52.5
        )
        df_raw["longitude"] = df_raw["areacd_clean"].map(
            lambda x: ONS_LA_CENTROIDS[x][1] if x in ONS_LA_CENTROIDS else -1.5
        )
        gdf = gpd.GeoDataFrame(
            df_raw,
            geometry=gpd.points_from_xy(df_raw["longitude"], df_raw["latitude"]),
            crs="EPSG:4326",
        )
    else:
        st.error("Could not locate point coordinates or area codes in the dataset.")
        st.stop()

    # Create mapping of Raw Header -> Plain English Label
    friendly_cols_map = {col: get_friendly_label(col) for col in gdf.columns if col != "geometry"}

    # --- Interactive Filtering Bar ---
    group_cols = [
        c for c in gdf.select_dtypes(include=["object"]).columns if c != "geometry" and c != "areacd_clean"
    ]

    col_f1, col_f2 = st.columns([1, 2])

    if group_cols:
        with col_f1:
            # Display plain language names in the dropdown selection
            selected_raw_attribute = st.selectbox(
                "Filter Category",
                group_cols,
                format_func=lambda x: friendly_cols_map.get(x, x),
            )
        with col_f2:
            unique_vals = ["All Locations / Categories"] + sorted(
                list(gdf[selected_raw_attribute].unique())
            )
            selected_val = st.selectbox("Select Specific Region or Value", unique_vals)

        if selected_val != "All Locations / Categories":
            filtered_gdf = gdf[gdf[selected_raw_attribute] == selected_val]
        else:
            filtered_gdf = gdf.copy()
    else:
        filtered_gdf = gdf.copy()
        selected_val = "All Data"

    st.markdown("---")

    # --- Main Visual Dashboard Layout ---
    col_map, col_analytics = st.columns([3, 2])

    # --- 1. Interactive Spatial Map ---
    with col_map:
        st.subheader("🗺️ Geographic Charging Point Locations")

        if not filtered_gdf.empty:
            centroid = [filtered_gdf.geometry.y.mean(), filtered_gdf.geometry.x.mean()]
            m = folium.Map(
                location=centroid,
                zoom_start=9 if selected_val != "All Locations / Categories" else 6,
                tiles=map_style,
                control_scale=True,
            )

            point_gdf = filtered_gdf[filtered_gdf.geometry.geom_type == "Point"]
            coords = [[point.y, point.x] for point in point_gdf.geometry]

            if map_mode == "Density Heatmap":
                HeatMap(
                    coords, radius=heatmap_radius, blur=15, min_opacity=0.4
                ).add_to(m)
            else:
                marker_cluster = MarkerCluster().add_to(m)
                popup_cols = [
                    c for c in filtered_gdf.columns if c not in ["geometry", "areacd_clean", "latitude", "longitude"]
                ][:4]

                for idx, row in point_gdf.head(1500).iterrows():
                    popup_html = "<div style='font-family: sans-serif; font-size: 12px;'>"
                    popup_html += "".join(
                        [
                            f"<b>{friendly_cols_map.get(col, col)}:</b> {row[col]}<br>"
                            for col in popup_cols
                        ]
                    )
                    popup_html += "</div>"

                    folium.CircleMarker(
                        location=[row.geometry.y, row.geometry.x],
                        radius=5,
                        color="#005A9C",
                        fill=True,
                        fill_color="#0080FF",
                        fill_opacity=0.8,
                        popup=folium.Popup(popup_html, max_width=250),
                    ).add_to(marker_cluster)

            st_folium(m, use_container_width=True, height=520)

    # --- 2. Dynamic Charts ---
    with col_analytics:
        st.subheader("📊 Visual Distribution Analytics")

        # Visual Chart 1: Bar Chart breakdown
        if group_cols:
            cat_counts = (
                filtered_gdf[selected_raw_attribute]
                .value_counts()
                .head(10)
                .reset_index()
            )
            friendly_name = friendly_cols_map.get(selected_raw_attribute, selected_raw_attribute)
            cat_counts.columns = [friendly_name, "Device Count"]

            fig_bar = px.bar(
                cat_counts,
                x="Device Count",
                y=friendly_name,
                orientation="h",
                title=f"Top 10 Locations by '{friendly_name}'",
                color="Device Count",
                color_continuous_scale=color_theme,
            )
            fig_bar.update_layout(
                yaxis={"categoryorder": "total ascending"},
                height=250,
                margin=dict(l=10, r=10, t=35, b=10),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # Visual Chart 2: Donut Chart breakdown
        if len(group_cols) > 1:
            sec_col = (
                group_cols[1]
                if group_cols[1] != selected_raw_attribute
                else group_cols[0]
            )
            friendly_sec_name = friendly_cols_map.get(sec_col, sec_col)
            
            # Temporarily rename columns for chart legend readability
            pie_data = filtered_gdf.head(200).rename(columns=friendly_cols_map)
            
            fig_pie = px.pie(
                pie_data,
                names=friendly_sec_name,
                title=f"Proportional Share by '{friendly_sec_name}'",
                hole=0.4,
                color_discrete_sequence=px.colors.sequential.Blues_r,
            )
            fig_pie.update_layout(
                height=240, margin=dict(l=10, r=10, t=35, b=10)
            )
            st.plotly_chart(fig_pie, use_container_width=True)

except Exception as e:
    st.error(f"Visualization Error: {str(e)}")
