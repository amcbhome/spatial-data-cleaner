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
    page_title="ONS Spatial Data Cleaner & Visualiser",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Header & Overview ---
st.title("🗺️ Spatial Data Cleaning & Validation Tool")
st.caption(
    "A Reproducible Analytical Pipeline (RAP) utility for processing UK spatial datasets, ONS Local Authority statistics, and EV infrastructure data."
)

with st.expander("ℹ️ How to use this tool"):
    st.markdown("""
    1. **Upload Data:** Select a CSV, GeoJSON, or GeoPackage file in the sidebar.
    2. **Automatic Cleaning:** The pipeline validates spatial geometries, deduplicates records, standardises strings, and normalises coordinate systems (CRS).
    3. **Automatic Mapping:** If point coordinates aren't present, the tool automatically maps standard ONS codes (`areacd` / `LADCD`) to geographic centroids.
    4. **Export:** Review summary metrics, inspect interactive maps and charts, view a detailed cleaning log, and export the clean dataset as GeoJSON.
    """)

# --- Reference Lookups & Sample Data ---
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

SAMPLE_CSV_DATA = """areacd,areanm,period,value,latitude,longitude
W06000024,Merthyr Tydfil,2024,42,51.7480,-3.3780
E06000001,Hartlepool,2024,18,54.6860,-1.2130
E08000025,Birmingham,2024,156,52.4862,-1.8904
E08000035,Leeds,2024,98,53.8008,-1.5491
S12000033,Aberdeen City,2024,54,57.1497,-2.0943
E09000001,City of London,2024,87,51.5127,-0.0918
"""


# --- Pipeline Logic ---
def clean_geospatial_pipeline(
    gdf: gpd.GeoDataFrame, target_crs: str = "EPSG:27700"
) -> tuple[gpd.GeoDataFrame, dict]:
    """Executes automated spatial data cleaning steps and logs methodology."""
    metrics = {"initial_count": len(gdf), "steps_log": []}

    # 1. Geometry Validation
    df_clean = gdf[gdf.geometry.notnull()].copy()
    df_clean = df_clean[df_clean.geometry.is_valid]
    invalid_dropped = metrics["initial_count"] - len(df_clean)
    metrics["invalid_geom_dropped"] = invalid_dropped
    metrics["steps_log"].append(
        f"**1. Geometry Check:** Checked spatial features. Dropped `{invalid_dropped}` null/invalid geometries."
    )

    # 2. Deduplication
    pre_dedup = len(df_clean)
    df_clean = df_clean.drop_duplicates()
    duplicates_dropped = pre_dedup - len(df_clean)
    metrics["duplicates_dropped"] = duplicates_dropped
    metrics["steps_log"].append(
        f"**2. Deduplication:** Removed `{duplicates_dropped}` exact duplicate records across all columns."
    )

    # 3. CRS Reprojection
    if df_clean.crs is None:
        df_clean.set_crs("EPSG:4326", inplace=True)
        metrics["steps_log"].append(
            "**3. CRS Alignment:** Unspecified Coordinate Reference System detected. Defaulted to `EPSG:4326` (WGS84)."
        )
    
    df_clean = df_clean.to_crs(target_crs)
    metrics["steps_log"].append(
        f"**3. CRS Reprojection:** Successfully transformed spatial coordinates to target system `{target_crs}`."
    )

    # 4. UK Mainland Spatial Boundary Check
    if target_crs == "EPSG:27700":
        uk_bounds = (0, 0, 700000, 1250000)
        pre_bounds = len(df_clean)
        df_clean = df_clean.cx[
            uk_bounds[0] : uk_bounds[2], uk_bounds[1] : uk_bounds[3]
        ]
        out_of_bounds_dropped = pre_bounds - len(df_clean)
        metrics["out_of_bounds_dropped"] = out_of_bounds_dropped
        metrics["steps_log"].append(
            f"**4. Spatial Bounding Filter:** Checked coordinates against British National Grid extent. Filtered `{out_of_bounds_dropped}` records falling outside mainland UK."
        )
    else:
        metrics["out_of_bounds_dropped"] = 0
        metrics["steps_log"].append(
            "**4. Spatial Bounding Filter:** Skipped (Bounding filter applies to EPSG:27700)."
        )

    # 5. String Normalisation
    modified_text_cols = []
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
                modified_text_cols.append(f"`{col}` (Uppercase GSS Code)")
            else:
                df_clean[col] = (
                    df_clean[col].astype(str).str.strip().str.lower().str.title()
                )
                modified_text_cols.append(f"`{col}` (Title Case)")

    metrics["steps_log"].append(
        f"**5. Text Normalisation:** Stripped leading/trailing whitespace and standardized schema formatting for columns: {', '.join(modified_text_cols) if modified_text_cols else 'None'}."
    )

    metrics["final_count"] = len(df_clean)
    return df_clean, metrics


# --- Sidebar Setup ---
st.sidebar.markdown("## 📁 Step 1: Input Data")
uploaded_file = st.sidebar.file_uploader(
    "Upload Spatial Dataset",
    type=["geojson", "csv", "gpkg", "json"],
    help="Upload CSV files with coordinates/area codes, or standard GeoJSON/GeoPackage files.",
)

st.sidebar.download_button(
    label="📥 Download Sample Test File",
    data=SAMPLE_CSV_DATA,
    file_name="ons_sample_dataset.csv",
    mime="text/csv",
    help="Download a clean ONS test file containing area codes and coordinates.",
)

st.sidebar.markdown("---")
st.sidebar.markdown("## ⚙️ Step 2: Processing Options")

target_crs = st.sidebar.selectbox(
    "Coordinate System (CRS)",
    options=["EPSG:27700", "EPSG:4326"],
    index=0,
    help="EPSG:27700 = British National Grid (Metres) | EPSG:4326 = WGS84 (Lat/Long)",
)

st.sidebar.markdown("---")
st.sidebar.markdown("## 🎨 Step 3: Map Controls")

map_style = st.sidebar.selectbox(
    "Map Background",
    options=["CartoDB positron", "OpenStreetMap", "CartoDB dark_matter"],
    index=0,
)
map_mode = st.sidebar.radio(
    "Data Display Mode",
    options=["Clustered Markers", "Density Heatmap"],
    index=0,
)

# --- Main Interface Logic ---
if uploaded_file is not None:
    try:
        file_ext = uploaded_file.name.split(".")[-1].lower()

        with st.spinner("Ingesting and processing dataset..."):
            if file_ext == "csv":
                df_raw = pd.read_csv(uploaded_file)
                cols_lower = {col.lower(): col for col in df_raw.columns}

                found_lat = next(
                    (
                        cols_lower[c]
                        for c in ["latitude", "lat", "y_coord", "y"]
                        if c in cols_lower
                    ),
                    None,
                )
                found_lon = next(
                    (
                        cols_lower[c]
                        for c in [
                            "longitude",
                            "long",
                            "lng",
                            "lon",
                            "x_coord",
                            "x",
                        ]
                        if c in cols_lower
                    ),
                    None,
                )
                code_col = next(
                    (
                        cols_lower[c]
                        for c in [
                            "areacd",
                            "ladcd",
                            "area_code",
                            "gss_code",
                            "lad23cd",
                        ]
                        if c in cols_lower
                    ),
                    None,
                )

                if found_lat and found_lon:
                    df_raw[found_lat] = pd.to_numeric(
                        df_raw[found_lat], errors="coerce"
                    )
                    df_raw[found_lon] = pd.to_numeric(
                        df_raw[found_lon], errors="coerce"
                    )
                    df_raw = df_raw.dropna(subset=[found_lat, found_lon])

                    raw_gdf = gpd.GeoDataFrame(
                        df_raw,
                        geometry=gpd.points_from_xy(
                            df_raw[found_lon], df_raw[found_lat]
                        ),
                        crs="EPSG:4326",
                    )
                elif code_col:
                    st.toast(
                        f"Matched area code column `{code_col}`. Applying ONS geographic lookup.",
                        icon="📍",
                    )
                    df_raw["areacd_clean"] = (
                        df_raw[code_col].astype(str).str.upper()
                    )

                    df_raw["latitude"] = df_raw["areacd_clean"].map(
                        lambda x: (
                            ONS_LA_CENTROIDS[x][0]
                            if x in ONS_LA_CENTROIDS
                            else None
                        )
                    )
                    df_raw["longitude"] = df_raw["areacd_clean"].map(
                        lambda x: (
                            ONS_LA_CENTROIDS[x][1]
                            if x in ONS_LA_CENTROIDS
                            else None
                        )
                    )

                    # Central UK fallback for unmatched entries
                    df_raw["latitude"] = df_raw["latitude"].fillna(52.5)
                    df_raw["longitude"] = df_raw["longitude"].fillna(-1.5)

                    raw_gdf = gpd.GeoDataFrame(
                        df_raw,
                        geometry=gpd.points_from_xy(
                            df_raw["longitude"], df_raw["latitude"]
                        ),
                        crs="EPSG:4326",
                    )
                else:
                    st.error(
                        f"❌ Could not detect coordinate headers or ONS area codes. Available headers: `{list(df_raw.columns)}`"
                    )
                    st.stop()
            else:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=f".{file_ext}"
                ) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                raw_gdf = gpd.read_file(tmp_path)

            # Run cleaning pipeline
            cleaned_gdf, metrics = clean_geospatial_pipeline(
                raw_gdf, target_crs=target_crs
            )

        # --- Section 1: Executive Key Metrics ---
        st.subheader("📊 Pipeline Results & Quality Summary")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Raw Records Read", f"{metrics['initial_count']:,}")
        m2.metric("Duplicates Dropped", f"{metrics['duplicates_dropped']:,}")
        m3.metric(
            "Out of Bounds Filtered", f"{metrics['out_of_bounds_dropped']:,}"
        )
        m4.metric(
            "Final Valid Records",
            f"{metrics['final_count']:,}",
            delta=f"{metrics['final_count'] - metrics['initial_count']} net change",
        )

        st.markdown("---")

        # --- Section 2: Visualisation Map ---
        st.subheader("🗺️ Interactive Spatial Map")
        map_gdf = cleaned_gdf.to_crs("EPSG:4326")

        if not map_gdf.empty:
            centroid = [map_gdf.geometry.y.mean(), map_gdf.geometry.x.mean()]
            m = folium.Map(
                location=centroid, zoom_start=7, tiles=map_style, control_scale=True
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

                for idx, row in point_gdf.head(2000).iterrows():
                    popup_html = "<br>".join(
                        [
                            f"<b>{col.title()}:</b> {row[col]}"
                            for col in popup_cols
                        ]
                    )
                    folium.CircleMarker(
                        location=[row.geometry.y, row.geometry.x],
                        radius=6,
                        color="#005A9C",
                        fill=True,
                        fill_color="#0080FF",
                        fill_opacity=0.8,
                        popup=folium.Popup(popup_html, max_width=300),
                    ).add_to(marker_cluster)

            st_folium(m, use_container_width=True, height=480)

        st.markdown("---")

        # --- Section 3: Data Inspection & Analytics ---
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.subheader("📈 Attribute Analytics")
            if "value" in cleaned_gdf.columns and "areanm" in cleaned_gdf.columns:
                fig = px.bar(
                    cleaned_gdf.head(15),
                    x="value",
                    y="areanm",
                    orientation="h",
                    title="Statistical Values by Area Name",
                    color="value",
                    color_continuous_scale="Blues",
                )
                fig.update_layout(
                    yaxis={"categoryorder": "total ascending"},
                    height=350,
                    margin=dict(l=10, r=10, t=40, b=10),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                cat_cols = [
                    c
                    for c in cleaned_gdf.select_dtypes(
                        include=["object"]
                    ).columns
                    if c != "geometry"
                ]
                if cat_cols:
                    selected_cat = st.selectbox(
                        "Group By Field", options=cat_cols
                    )
                    counts = (
                        cleaned_gdf[selected_cat]
                        .value_counts()
                        .head(10)
                        .reset_index()
                    )
                    counts.columns = [selected_cat, "Count"]
                    fig = px.bar(
                        counts,
                        x="Count",
                        y=selected_cat,
                        orientation="h",
                        title=f"Top 10 Values in '{selected_cat}'",
                        color="Count",
                        color_continuous_scale="Blues",
                    )
                    fig.update_layout(
                        yaxis={"categoryorder": "total ascending"},
                        height=350,
                        margin=dict(l=10, r=10, t=40, b=10),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No categorical text columns found for aggregation.")

        with col_right:
            st.subheader("📋 Clean Data Table Preview")
            st.dataframe(
                cleaned_gdf.drop(columns="geometry", errors="ignore").head(100),
                use_container_width=True,
                height=350,
            )

        st.markdown("---")

        # --- Section 4: Cleaning Methodology & Log ---
        st.subheader("📜 Pipeline Execution Log & Methodology")
        with st.expander("🔍 Click to view step-by-step cleaning summary", expanded=True):
            st.markdown(
                f"**Input Dataset:** `{uploaded_file.name}` | **Original Format:** `{file_ext.upper()}`"
            )
            st.markdown("---")
            for step in metrics["steps_log"]:
                st.markdown(f"- {step}")

        st.markdown("---")

        # --- Section 5: Export Options ---
        st.subheader("💾 Export Processed Dataset")

        col_dl1, col_dl2 = st.columns([1, 3])
        with col_dl1:
            geojson_bytes = cleaned_gdf.to_crs("EPSG:4326").to_json()
            st.download_button(
                label="📥 Download Clean GeoJSON",
                data=geojson_bytes,
                file_name=f"clean_{uploaded_file.name.split('.')[0]}.geojson",
                mime="application/geo+json",
                use_container_width=True,
            )
        with col_dl2:
            st.caption(
                "Exported GeoJSON files are normalized to standard WGS84 (`EPSG:4326`) geographic coordinates, compatible with QGIS, ArcGIS, and web mapping frameworks."
            )

    except Exception as e:
        st.error(f"An unexpected error occurred during processing: {str(e)}")

else:
    # Empty State Guidance
    st.info(
        "👈 Please upload a dataset in the sidebar or click 'Download Sample Test File' to get started."
    )
