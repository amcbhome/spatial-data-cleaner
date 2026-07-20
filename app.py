import folium
from folium.plugins import HeatMap, MarkerCluster
import geopandas as gpd
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# --- Page Configuration ---
st.set_page_config(
    page_title="ONS Local Authority EV Chargers Explorer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Raw ONS / DfT dataset URL
DEFAULT_GITHUB_URL = "https://raw.githubusercontent.com/amcbhome/spatial-data-cleaner/main/electric-vehicle-public-charging-devices.csv"

# ONS GSS Centroid Lookup Table
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

# Regional/National Aggregates to exclude so ONLY Local Authorities remain
AGGREGATE_ENTRIES = {
    "United Kingdom",
    "England",
    "Scotland",
    "Wales",
    "Northern Ireland",
    "North East",
    "North West",
    "Yorkshire and The Humber",
    "East Midlands",
    "West Midlands",
    "East of England",
    "London",
    "South East",
    "South West",
    "Great Britain",
}


@st.cache_data
def load_dataset(url: str) -> pd.DataFrame:
    return pd.read_csv(url)


# --- Header & Context ---
st.title("⚡ ONS Public Electric Vehicle Chargers: Local Authorities")
st.caption(
    "Source: Office for National Statistics (ONS) / Department for Transport (DfT) Explore Local Statistics Indicator"
)

with st.expander("ℹ️ About This Local Authority Dataset", expanded=False):
    st.markdown(
        """
    This application isolates **Local Authority District** entries from the official 4-field ONS local indicator dataset:
    
    | Field Name | Description |
    | :--- | :--- |
    | **`areacd`** | Official 9-character ONS GSS Local Authority code (e.g. `E08000025`). |
    | **`areanm`** | Name of the specific Local Authority Council (e.g. `Coventry`, `Leeds`). |
    | **`period`** | Time frame / reporting period. |
    | **`value`** | Recorded count or rate of public EV charging devices per local authority. |
    """
    )

st.markdown("---")

# --- Sidebar Controls ---
st.sidebar.title("🎨 Map Controls")
map_style = st.sidebar.selectbox(
    "Basemap Theme",
    ["CartoDB positron", "OpenStreetMap", "CartoDB dark_matter"],
    index=0,
)
map_mode = st.sidebar.radio(
    "Spatial Display Mode",
    ["Clustered Point Markers", "Density Heatmap"],
    index=0,
)

# --- Load & Process Data ---
try:
    df_raw = load_dataset(DEFAULT_GITHUB_URL)

    # Detect area name column (`areanm`)
    areanm_col = next(
        (
            c
            for c in df_raw.columns
            if c.lower()
            in ["areanm", "ladnm", "local_authority_name", "region", "areacd"]
        ),
        None,
    )

    if areanm_col:
        # Filter out national and regional aggregate entries
        raw_unique = df_raw[areanm_col].dropna().unique()
        la_options = sorted(
            [
                name
                for name in raw_unique
                if str(name).strip() not in AGGREGATE_ENTRIES
            ]
        )

        # Default to Coventry if present
        default_idx = 0
        for i, opt in enumerate(la_options):
            if "coventry" in str(opt).lower():
                default_idx = i
                break

        selected_la = st.selectbox(
            "🏛️ Select Local Authority (`areanm`):",
            options=la_options,
            index=default_idx,
            help="Select a specific UK local authority council to view its ONS metrics and map location.",
        )

        filtered_df = df_raw[df_raw[areanm_col] == selected_la].copy()
    else:
        selected_la = "All Local Authorities"
        filtered_df = df_raw.copy()

    # Detect area code column (`areacd`) or lat/lon coordinates
    cols_lower = {col.lower(): col for col in filtered_df.columns}
    found_lat = next(
        (cols_lower[c] for c in ["latitude", "lat", "y"] if c in cols_lower),
        None,
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
        filtered_df[found_lat] = pd.to_numeric(
            filtered_df[found_lat], errors="coerce"
        )
        filtered_df[found_lon] = pd.to_numeric(
            filtered_df[found_lon], errors="coerce"
        )
        filtered_df = filtered_df.dropna(subset=[found_lat, found_lon])
        gdf = gpd.GeoDataFrame(
            filtered_df,
            geometry=gpd.points_from_xy(
                filtered_df[found_lon], filtered_df[found_lat]
            ),
            crs="EPSG:4326",
        )
    elif code_col:
        filtered_df["areacd_clean"] = (
            filtered_df[code_col].astype(str).str.upper()
        )
        filtered_df["latitude"] = filtered_df["areacd_clean"].map(
            lambda x: ONS_LA_CENTROIDS[x][0] if x in ONS_LA_CENTROIDS else 52.5
        )
        filtered_df["longitude"] = filtered_df["areacd_clean"].map(
            lambda x: ONS_LA_CENTROIDS[x][1] if x in ONS_LA_CENTROIDS else -1.5
        )
        gdf = gpd.GeoDataFrame(
            filtered_df,
            geometry=gpd.points_from_xy(
                filtered_df["longitude"], filtered_df["latitude"]
            ),
            crs="EPSG:4326",
        )
    else:
        st.error("Could not parse coordinates or area codes in dataset.")
        st.stop()

    # --- Local Authority KPI Summary ---
    st.markdown(f"### 📊 Local Authority Summary: **{selected_la}**")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Local Authority (`areanm`)", str(selected_la))

    # Display GSS Area Code
    gss_val = gdf[code_col].iloc[0] if code_col and not gdf.empty else "N/A"
    m2.metric("Council Area Code (`areacd`)", str(gss_val))

    # Display Period
    period_col = next(
        (cols_lower[c] for c in ["period", "year"] if c in cols_lower), None
    )
    period_val = (
        gdf[period_col].iloc[0] if period_col and not gdf.empty else "Latest"
    )
    m3.metric("Time Period (`period`)", str(period_val))

    # Display Value
    val_col = next(
        (cols_lower[c] for c in ["value", "chargers"] if c in cols_lower), None
    )
    if val_col:
        m4.metric("EV Charger Metric (`value`)", f"{gdf[val_col].sum():,.1f}")
    else:
        m4.metric("Mapped Records", f"{len(gdf):,}")

    st.markdown("---")

    # --- Interactive Map & Data Table ---
    col_map, col_table = st.columns([3, 2])

    with col_map:
        st.subheader(f"🗺️ Spatial Map for {selected_la}")

        if not gdf.empty:
            lat_mean = float(gdf.geometry.y.mean())
            lon_mean = float(gdf.geometry.x.mean())

            m = folium.Map(
                location=[lat_mean, lon_mean],
                zoom_start=11,
                tiles=map_style,
                control_scale=True,
            )

            coords = [[p.y, p.x] for p in gdf.geometry]

            if map_mode == "Density Heatmap":
                HeatMap(coords, radius=18, blur=15, min_opacity=0.4).add_to(m)
            else:
                marker_cluster = MarkerCluster().add_to(m)
                for idx, row in gdf.head(1000).iterrows():
                    popup_html = (
                        "<div style='font-family: sans-serif; font-size: 12px;'>"
                    )
                    popup_html += (
                        f"<b>Local Authority (areanm):</b> {selected_la}<br>"
                    )
                    if code_col:
                        popup_html += (
                            f"<b>Area Code (areacd):</b> {row[code_col]}<br>"
                        )
                    if period_col:
                        popup_html += f"<b>Time Period (period):</b> {row[period_col]}<br>"
                    if val_col:
                        popup_html += f"<b>Charger Metric (value):</b> {row[val_col]}<br>"
                    popup_html += "</div>"

                    folium.CircleMarker(
                        location=[row.geometry.y, row.geometry.x],
                        radius=7,
                        color="#005A9C",
                        fill=True,
                        fill_color="#0080FF",
                        fill_opacity=0.8,
                        popup=folium.Popup(popup_html, max_width=250),
                    ).add_to(marker_cluster)

            st_folium(
                m,
                use_container_width=True,
                height=480,
                key=f"map_render_{selected_la}",
            )

    with col_table:
        st.subheader("📋 Local Authority Data Table")

        display_df = gdf.drop(
            columns=["geometry", "areacd_clean", "latitude", "longitude"],
            errors="ignore",
        )
        st.dataframe(
            display_df,
            use_container_width=True,
            height=360,
        )

        geojson_bytes = gdf.to_crs("EPSG:4326").to_json()
        st.download_button(
            label=f"📥 Export {selected_la} GeoJSON",
            data=geojson_bytes,
            file_name=f"{str(selected_la).lower().replace(' ', '_')}_la_data.geojson",
            mime="application/geo+json",
            use_container_width=True,
        )

except Exception as e:
    st.error(f"App Execution Error: {str(e)}")
