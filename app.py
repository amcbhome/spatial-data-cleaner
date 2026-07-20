import tempfile
import folium
import geopandas as gpd
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# Page configuration
st.set_page_config(
    page_title="Spatial Data Cleaning Pipeline", page_icon="🧼", layout="wide"
)

st.title("🧼 Spatial Data Cleaning & Validation Pipeline")
st.markdown(
    "Upload raw open data or geospatial feeds (GeoJSON, CSV, GPKG) to clean, validate, and reproject for downstream analysis."
)


def clean_geospatial_pipeline(
    gdf: gpd.GeoDataFrame, target_crs: str = "EPSG:27700"
) -> tuple[gpd.GeoDataFrame, dict]:
    """Runs data cleaning, spatial validation, and schema normalization."""
    metrics = {"initial_count": len(gdf)}

    # 1. Handle Null / Invalid Geometries
    df_clean = gdf[gdf.geometry.notnull()].copy()
    df_clean = df_clean[df_clean.geometry.is_valid]
    metrics["invalid_geom_dropped"] = metrics["initial_count"] - len(df_clean)

    # 2. Deduplication
    pre_dedup = len(df_clean)
    df_clean = df_clean.drop_duplicates()
    metrics["duplicates_dropped"] = pre_dedup - len(df_clean)

    # 3. CRS Normalization
    if df_clean.crs is None:
        df_clean.set_crs("EPSG:4326", inplace=True)

    df_clean = df_clean.to_crs(target_crs)

    # 4. Bounding Box Filter (UK Mainland EPSG:27700 Bounds)
    if target_crs == "EPSG:27700":
        uk_bounds = (0, 0, 700000, 1250000)
        pre_bounds = len(df_clean)
        df_clean = df_clean.cx[
            uk_bounds[0] : uk_bounds[2], uk_bounds[1] : uk_bounds[3]
        ]
        metrics["out_of_bounds_dropped"] = pre_bounds - len(df_clean)
    else:
        metrics["out_of_bounds_dropped"] = 0

    # 5. String Normalization for Object Columns
    for col in df_clean.select_dtypes(include=["object"]).columns:
        if col != "geometry":
            df_clean[col] = (
                df_clean[col].astype(str).str.strip().str.lower().str.title()
            )

    metrics["final_count"] = len(df_clean)
    return df_clean, metrics


# --- Sidebar Setup ---
st.sidebar.header("Configuration")
uploaded_file = st.sidebar.file_uploader(
    "Upload Spatial Dataset", type=["geojson", "csv", "gpkg", "json"]
)

target_crs = st.sidebar.selectbox(
    "Target CRS",
    options=["EPSG:27700", "EPSG:4326"],
    index=0,
    help="EPSG:27700 = British National Grid (Metres) | EPSG:4326 = WGS84 (Lat/Long)",
)

lat_col = st.sidebar.text_input("CSV Latitude Column Name", value="latitude")
lon_col = st.sidebar.text_input("CSV Longitude Column Name", value="longitude")

# --- Main App Logic ---
if uploaded_file is not None:
    try:
        # Load Raw File
        file_ext = uploaded_file.name.split(".")[-1].lower()

        if file_ext == "csv":
            df_raw = pd.read_csv(uploaded_file)
            if lat_col in df_raw.columns and lon_col in df_raw.columns:
                raw_gdf = gpd.GeoDataFrame(
                    df_raw,
                    geometry=gpd.points_from_xy(
                        df_raw[lon_col], df_raw[lat_col]
                    ),
                    crs="EPSG:4326",
                )
            else:
                st.error(
                    f"Could not find coordinate columns '{lat_col}' and '{lon_col}' in CSV."
                )
                st.stop()
        else:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=f".{file_ext}"
            ) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            raw_gdf = gpd.read_file(tmp_path)

        st.success(
            f"Successfully loaded `{uploaded_file.name}` ({len(raw_gdf)} records)"
        )

        # Run Cleaning Pipeline
        cleaned_gdf, metrics = clean_geospatial_pipeline(
            raw_gdf, target_crs=target_crs
        )

        # Display Metrics
        st.subheader("📊 Pipeline Execution Summary")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Raw Records", metrics["initial_count"])
        m2.metric("Duplicates Removed", metrics["duplicates_dropped"])
        m3.metric("Out of Bounds Removed", metrics["out_of_bounds_dropped"])
        m4.metric("Valid Clean Records", metrics["final_count"])

        # Tabs for Preview & Map Visualization
        tab1, tab2 = st.columns([1, 1])

        with tab1:
            st.subheader("📋 Cleaned Dataset Preview")
            st.dataframe(
                cleaned_gdf.drop(columns="geometry", errors="ignore").head(50),
                use_container_width=True,
            )

        with tab2:
            st.subheader("🗺️ Spatial Distribution Map")
            # Convert to EPSG:4326 for Leaflet plotting
            map_gdf = cleaned_gdf.to_crs("EPSG:4326")

            if not map_gdf.empty:
                centroid = [
                    map_gdf.geometry.y.mean(),
                    map_gdf.geometry.x.mean(),
                ]
                m = folium.Map(location=centroid, zoom_start=10)

                # Add sample points (limit to 500 for UI responsiveness)
                for idx, row in map_gdf.head(500).iterrows():
                    if row.geometry.geom_type == "Point":
                        folium.CircleMarker(
                            location=[row.geometry.y, row.geometry.x],
                            radius=4,
                            color="#1f77b4",
                            fill=True,
                        ).add_to(m)

                st_folium(m, width=500, height=400)

        # Download Cleaned Dataset
        st.subheader("💾 Export Cleaned Dataset")
        geojson_bytes = cleaned_gdf.to_crs("EPSG:4326").to_json()

        st.download_button(
            label="Download Cleaned GeoJSON",
            data=geojson_bytes,
            file_name=f"clean_{uploaded_file.name.split('.')[0]}.geojson",
            mime="application/geo+json",
        )

    except Exception as e:
        st.error(f"Error processing file: {str(e)}")

else:
    st.info("👈 Upload a spatial file in the sidebar to run the pipeline.")
