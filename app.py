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

    # --- Interactive Filtering Bar ---
    group_cols = [
        c for c in gdf.select_dtypes(include=["object"]).columns if c != "geometry"
    ]

    col_f1, col_f2 = st.columns([1, 2])

    if group_cols:
        with col_f1:
            filter_attribute = st.selectbox("Categorical Feature", group_cols)
        with col_f2:
            unique_vals = ["All Regions / Categories"] + sorted(
                list(gdf[filter_attribute].unique())
            )
            selected_val = st.selectbox("Interactive Filter", unique_vals)

        if selected_val != "All Regions / Categories":
            filtered_gdf = gdf[gdf[filter_attribute] == selected_val]
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
        st.subheader("🗺️ Geographic Infrastructure Distribution")

        if not filtered_gdf.empty:
            centroid = [filtered_gdf.geometry.y.mean(), filtered_gdf.geometry.x.mean()]
            m = folium.Map(
                location=centroid,
                zoom_start=9 if selected_val != "All Regions / Categories" else 6,
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
                    c for c in filtered_gdf.columns if c not in ["geometry"]
                ][:4]

                for idx, row in point_gdf.head(1500).iterrows():
                    popup_html = "<div style='font-family: sans-serif; font-size: 12px;'>"
                    popup_html += "".join(
                        [
                            f"<b>{col.title()}:</b> {row[col]}<br>"
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
                filtered_gdf[filter_attribute]
                .value_counts()
                .head(10)
                .reset_index()
            )
            cat_counts.columns = [filter_attribute, "Device Count"]

            fig_bar = px.bar(
                cat_counts,
                x="Device Count",
                y=filter_attribute,
                orientation="h",
                title=f"Top Features in '{filter_attribute}'",
                color="Device Count",
                color_continuous_scale=color_theme,
            )
            fig_bar.update_layout(
                yaxis={"categoryorder": "total ascending"},
                height=250,
                margin=dict(l=10, r=10, t=35, b=10),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # Visual Chart 2: Sunburst / Donut proportional breakdown
        if len(group_cols) > 1:
            sec_col = (
                group_cols[1]
                if group_cols[1] != filter_attribute
                else group_cols[0]
            )
            fig_pie = px.pie(
                filtered_gdf.head(200),
                names=sec_col,
                title=f"Distribution by '{sec_col}'",
                hole=0.4,
                color_discrete_sequence=px.colors.sequential.Blues_r,
            )
            fig_pie.update_layout(
                height=240, margin=dict(l=10, r=10, t=35, b=10)
            )
            st.plotly_chart(fig_pie, use_container_width=True)

except Exception as e:
    st.error(f"Visualization Error: {str(e)}")
