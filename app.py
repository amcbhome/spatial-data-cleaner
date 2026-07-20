import tempfile
import folium
from folium.plugins import HeatMap, MarkerCluster
import geopandas as gpd
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

# --- Page Configuration ---
st.set_page_config(
    page_title="Geospatial Data Pipeline & Regional Analytics",
    page_icon="🗺️",
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


# --- Pipeline Logic ---
def clean_geospatial_pipeline(
    gdf: gpd.GeoDataFrame, target_crs: str = "EPSG:27700"
) -> tuple[gpd.GeoDataFrame, dict]:
    """Executes automated spatial data cleaning steps and logs methodology."""
    metrics = {"initial_count": len(gdf), "steps_log": []}

    # 1. Geometry Check
    df_clean = gdf[gdf.geometry.notnull()].copy()
    df_clean = df_clean[df_clean.geometry.is_valid]
    invalid_dropped = metrics["initial_count"] - len(df_clean)
    metrics["invalid_geom_dropped"] = invalid_dropped
    metrics["steps_log"].append(
        f"**1. Geometry Check:** Validated spatial features. Filtered `{invalid_dropped}` null or invalid geometries."
    )

    # 2. Deduplication
    pre_dedup = len(df_clean)
    df_clean = df_clean.drop_duplicates()
    duplicates_dropped = pre_dedup - len(df_clean)
    metrics["duplicates_dropped"] = duplicates_dropped
    metrics["steps_log"].append(
        f"**2. Deduplication:** Identified and dropped `{duplicates_dropped}` exact duplicate records across all columns."
    )

    # 3. CRS Alignment
    if df_clean.crs is None:
        df_clean.set_crs("EPSG:4326", inplace=True)
        metrics["steps_log"].append(
            "**3. CRS Alignment:** Unspecified spatial reference system detected. Defaulted to `EPSG:4326` (WGS84)."
        )

    df_clean = df_clean.to_crs(target_crs)
    metrics["steps_log"].append(
        f"**3. CRS Reprojection:** Standardized coordinate system to `{target_crs}`."
    )

    # 4. Spatial Bounding
    if target_crs == "EPSG:27700":
        uk_bounds = (0, 0, 700000, 1250000)
        pre_bounds = len(df_clean)
        df_clean = df_clean.cx[
            uk_bounds[0] : uk_bounds[2], uk_bounds[1] : uk_bounds[3]
        ]
        out_of_bounds_dropped = pre_bounds - len(df_clean)
        metrics["out_of_bounds_dropped"] = out_of_bounds_dropped
        metrics["steps_log"].append(
            f"**4. Spatial Bounding:** Checked coordinates against British National Grid extents. Removed `{out_of_bounds_dropped}` out-of-bounds records."
        )
    else:
        metrics["out_of_bounds_dropped"] = 0

    # 5. Schema Normalisation
    for col in df_clean.select_dtypes(include=["object"]).columns:
        if col != "geometry":
            if col.lower() in [
                "areacd",
                "ladcd",
                "area_code",
                "gss_code",
                "lad23cd",
            ]:
                df_clean[col] = df_clean[col].astype(str).str.strip().str.upper()
            else:
                df_clean[col] = (
                    df_clean[col].astype(str).str.strip().str.lower().str.title()
                )

    metrics["steps_log"].append(
        "**5. Schema Normalisation:** Stripped whitespace and standardized text fields to uppercase GSS codes and title case labels."
    )
    metrics["final_count"] = len(df_clean)

    return df_clean, metrics


# --- Cached Data Loaders ---
@st.cache_data
def load_csv_from_url(url: str) -> pd.DataFrame:
    return pd.read_csv(url)


# --- Sidebar Setup ---
st.sidebar.title("🛠️ Control Panel")

data_source = st.sidebar.radio(
    "Data Source",
    ["GitHub Public EV Dataset", "Upload Custom File"],
    index=0,
)

if data_source == "Upload Custom File":
    uploaded_file = st.sidebar.file_uploader(
        "Upload File", type=["geojson", "csv", "gpkg"]
    )
else:
    uploaded_file = None

st.sidebar.markdown("---")
target_crs = st.sidebar.selectbox(
    "Target CRS", ["EPSG:27700", "EPSG:4326"], index=0
)
map_style = st.sidebar.selectbox(
    "Map Tiles", ["CartoDB positron", "OpenStreetMap", "CartoDB dark_matter"]
)
map_mode = st.sidebar.radio(
    "Display Mode", ["Clustered Markers", "Density Heatmap"]
)

# --- Header Section ---
st.title("🗺️ DfT Public EV Charging Infrastructure Pipeline")
st.caption(
    "Interactive Reproducible Analytical Pipeline (RAP) demonstrating automated cleaning, spatial mapping, and regional statistical summaries."
)

# --- Ingestion & Parsing ---
try:
    if uploaded_file is not None:
        file_ext = uploaded_file.name.split(".")[-1].lower()
        if file_ext == "csv":
            df_raw = pd.read_csv(uploaded_file)
        else:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=f".{file_ext}"
            ) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            raw_gdf = gpd.read_file(tmp_path)
    else:
        df_raw = load_csv_from_url(DEFAULT_GITHUB_URL)
        file_ext = "csv"

    if file_ext == "csv":
        cols_lower = {col.lower(): col for col in df_raw.columns}
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
            df_raw[found_lat] = pd.to_numeric(df_raw[found_lat], errors="coerce")
            df_raw[found_lon] = pd.to_numeric(df_raw[found_lon], errors="coerce")
            df_raw = df_raw.dropna(subset=[found_lat, found_lon])
            raw_gdf = gpd.GeoDataFrame(
                df_raw,
                geometry=gpd.points_from_xy(
                    df_raw[found_lon], df_raw[found_lat]
                ),
                crs="EPSG:4326",
            )
        elif code_col:
            st.toast(f"Matched area code column `{code_col}`. Applying ONS geographic lookup.", icon="📍")
            df_raw["areacd_clean"] = df_raw[code_col].astype(str).str.upper()
            df_raw["latitude"] = df_raw["areacd_clean"].map(
                lambda x: ONS_LA_CENTROIDS[x][0] if x in ONS_LA_CENTROIDS else 52.5
            )
            df_raw["longitude"] = df_raw["areacd_clean"].map(
                lambda x: ONS_LA_CENTROIDS[x][1] if x in ONS_LA_CENTROIDS else -1.5
            )
            raw_gdf = gpd.GeoDataFrame(
                df_raw,
                geometry=gpd.points_from_xy(
                    df_raw["longitude"], df_raw["latitude"]
                ),
                crs="EPSG:4326",
            )
        else:
            st.error(f"Could not parse coordinates or area codes. Headers found: `{list(df_raw.columns)}`")
            st.stop()

    # Run Pipeline
    cleaned_gdf, metrics = clean_geospatial_pipeline(
        raw_gdf, target_crs=target_crs
    )

    # ==========================================
    # PRESENTATION STEP 1: CLEANING AUDIT
    # ==========================================
    st.subheader("1. Data Pipeline & Quality Audit")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Raw Records Ingested", f"{metrics['initial_count']:,}")
    m2.metric("Duplicates Filtered", f"{metrics['duplicates_dropped']:,}")
    m3.metric("Out of Bounds Dropped", f"{metrics['out_of_bounds_dropped']:,}")
    m4.metric("Valid Production Records", f"{metrics['final_count']:,}")

    with st.expander("🔍 View Step-by-Step Data Quality Log", expanded=False):
        for step in metrics["steps_log"]:
            st.markdown(f"- {step}")

    st.markdown("---")

    # ==========================================
    # PRESENTATION STEP 2: REGIONAL FILTER & STATS
    # ==========================================
    st.subheader("2. Interactive Regional Statistical Summary")

    # Identify area grouping columns dynamically
    group_cols = [
        c
        for c in cleaned_gdf.select_dtypes(include=["object"]).columns
        if c != "geometry"
    ]

    selected_region = "All Regions"
    filtered_gdf = cleaned_gdf.copy()

    if group_cols:
        col_select1, col_select2 = st.columns([1, 2])
        with col_select1:
            region_col = st.selectbox("Select Filter Column", group_cols)
            region_list = ["All Regions"] + sorted(
                list(cleaned_gdf[region_col].unique())
            )
            selected_region = st.selectbox("Filter Specific Value", region_list)

        if selected_region != "All Regions":
            filtered_gdf = cleaned_gdf[
                cleaned_gdf[region_col] == selected_region
            ]

        with col_select2:
            s1, s2, s3 = st.columns(3)
            s1.metric(
                "Selected Area Count",
                f"{len(filtered_gdf):,}",
                delta=f"{len(filtered_gdf) / len(cleaned_gdf):.1%} of total dataset",
            )

            # Summarize numeric values if present (e.g., charger counts or values)
            num_cols = [
                c
                for c in filtered_gdf.select_dtypes(include=["number"]).columns
                if c.lower() not in ["latitude", "longitude", "lat", "lon"]
            ]
            if len(num_cols) > 0:
                s2.metric(
                    f"Mean {num_cols[0].title()}",
                    f"{filtered_gdf[num_cols[0]].mean():.1f}",
                )
                s3.metric(
                    f"Total {num_cols[0].title()}",
                    f"{filtered_gdf[num_cols[0]].sum():,.0f}",
                )
            else:
                s2.metric("Target Coordinate System", target_crs)
                s3.metric("Spatial Feature Type", "Point")

    st.markdown("---")

    # ==========================================
    # PRESENTATION STEP 3: VISUALISATION MAP & TABLE
    # ==========================================
    st.subheader("3. Spatial Map & Feature Inspection")

    col_map, col_chart = st.columns([2, 1])

    with col_map:
        map_gdf = filtered_gdf.to_crs("EPSG:4326")
        if not map_gdf.empty:
            centroid = [map_gdf.geometry.y.mean(), map_gdf.geometry.x.mean()]
            m = folium.Map(
                location=centroid,
                zoom_start=9 if selected_region != "All Regions" else 6,
                tiles=map_style,
            )

            point_gdf = map_gdf[map_gdf.geometry.geom_type == "Point"]
            coords = [[point.y, point.x] for point in point_gdf.geometry]

            if map_mode == "Density Heatmap":
                HeatMap(coords, radius=12, blur=15, min_opacity=0.4).add_to(m)
            else:
                marker_cluster = MarkerCluster().add_to(m)
                popup_cols = [
                    c for c in map_gdf.columns if c not in ["geometry"]
                ][:5]

                for idx, row in point_gdf.head(1500).iterrows():
                    popup_html = "<br>".join(
                        [
                            f"<b>{col.title()}:</b> {row[col]}"
                            for col in popup_cols
                        ]
                    )
                    folium.CircleMarker(
                        location=[row.geometry.y, row.geometry.x],
                        radius=5,
                        color="#005A9C",
                        fill=True,
                        fill_color="#0080FF",
                        fill_opacity=0.8,
                        popup=folium.Popup(popup_html, max_width=250),
                    ).add_to(marker_cluster)

            st_folium(m, use_container_width=True, height=450)

    with col_chart:
        st.markdown(f"**Cleaned Records Table ({selected_region})**")
        st.dataframe(
            filtered_gdf.drop(columns="geometry", errors="ignore").head(50),
            use_container_width=True,
            height=250,
        )

        geojson_bytes = filtered_gdf.to_crs("EPSG:4326").to_json()
        st.download_button(
            label="📥 Export Region GeoJSON",
            data=geojson_bytes,
            file_name=f"{selected_region.lower().replace(' ', '_')}_clean.geojson",
            mime="application/geo+json",
            use_container_width=True,
        )

except Exception as e:
    st.error(f"App Execution Error: {str(e)}")
