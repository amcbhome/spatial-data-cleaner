import folium
from folium.plugins import HeatMap, MarkerCluster
import geopandas as gpd
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# --- Page Configuration ---
st.set_page_config(
    page_title="Department for Transport EV Charging Explorer",
    page_icon="⚡",
    layout="wide",
)

DEFAULT_GITHUB_URL = "https://raw.githubusercontent.com/amcbhome/spatial-data-cleaner/main/electric-vehicle-public-charging-devices.csv"

# Centroid lookup for fallback area-code mapping
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


# --- Header Relevant to Dataset ---
st.title("⚡ Department for Transport Public EV Charging Infrastructure Explorer")
st.caption(
    "Interactive spatial analytics dashboard for exploring public electric vehicle charging device distribution across UK local authorities."
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

# --- Load & Parse Data ---
try:
    df_raw = load_dataset(DEFAULT_GITHUB_URL)

    # Detect region or local authority name column
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
        region_options = sorted(list(df_raw[areanm_col].dropna().unique()))

        # Default to Coventry if present
        default_idx = 0
        for i, opt in enumerate(region_options):
            if "coventry" in str(opt).lower():
                default_idx = i
                break

        selected_region = st.selectbox(
            "📍 Select Local Authority / Region:",
            options=region_options,
            index=default_idx,
            help="Selecting a region updates both the summary metrics and forces the map to re-center over that specific area code.",
        )

        filtered_df = df_raw[df_raw[areanm_col] == selected_region].copy()
    else:
        selected_region = "All Regions"
        filtered_df = df_raw.copy()

    # Parse spatial coordinates
    cols_lower = {col.lower(): col for col in filtered_df.columns}
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

    # --- Regional Profile Summary ---
    st.markdown(f"### 📊 Summary Profile: **{selected_region}**")

    m1, m2, m3 = st.columns(3)
    m1.metric("Selected Region", str(selected_region))

    num_cols = [
        c
        for c in gdf.select_dtypes(include=["number"]).columns
        if c.lower() not in ["latitude", "longitude", "lat", "lon"]
    ]

    if num_cols:
        m2.metric(
            f"Total {num_cols[0].replace('_', ' ').title()}",
            f"{gdf[num_cols[0]].sum():,.0f}",
        )
        m3.metric("Records Found", f"{len(gdf):,}")
    else:
        m2.metric("Mapped Locations", f"{len(gdf):,}")
        m3.metric("Data Source", "DfT Public Dataset")

    st.markdown("---")

    # --- Interactive Map Section ---
    col_map, col_table = st.columns([3, 2])

    with col_map:
        st.subheader(f"🗺️ Charging Points in {selected_region}")

        if not gdf.empty:
            # 1. Calculate new center coordinates dynamically
            lat_mean = float(gdf.geometry.y.mean())
            lon_mean = float(gdf.geometry.x.mean())

            # 2. Build fresh map instance
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
                popup_cols = [
                    c
                    for c in gdf.columns
                    if c.lower()
                    not in [
                        "geometry",
                        "latitude",
                        "longitude",
                        "period",
                        "year",
                    ]
                ][:4]

                for idx, row in gdf.head(1000).iterrows():
                    popup_html = (
                        "<div style='font-family: sans-serif; font-size: 12px;'>"
                    )
                    popup_html += f"<b>Region:</b> {selected_region}<br>"
                    popup_html += "".join(
                        [
                            f"<b>{col.replace('_', ' ').title()}:</b> {row[col]}<br>"
                            for col in popup_cols
                        ]
                    )
                    popup_html += "</div>"

                    folium.CircleMarker(
                        location=[row.geometry.y, row.geometry.x],
                        radius=6,
                        color="#005A9C",
                        fill=True,
                        fill_color="#0080FF",
                        fill_opacity=0.8,
                        popup=folium.Popup(popup_html, max_width=250),
                    ).add_to(marker_cluster)

            # 3. Force re-render on selection change using unique key
            st_folium(
                m,
                use_container_width=True,
                height=500,
                key=f"map_render_{selected_region}",
            )

    with col_table:
        st.subheader("📋 Region Data Inspection")

        preview_df = gdf.drop(
            columns=["geometry", "areacd_clean"], errors="ignore"
        )
        st.dataframe(
            preview_df,
            use_container_width=True,
            height=380,
        )

        geojson_bytes = gdf.to_crs("EPSG:4326").to_json()
        st.download_button(
            label=f"📥 Export {selected_region} Data (GeoJSON)",
            data=geojson_bytes,
            file_name=f"{str(selected_region).lower().replace(' ', '_')}_ev_data.geojson",
            mime="application/geo+json",
            use_container_width=True,
        )

except Exception as e:
    st.error(f"App Execution Error: {str(e)}")
