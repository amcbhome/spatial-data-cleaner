import tempfile
import folium
from folium.plugins import HeatMap, MarkerCluster
import geopandas as gpd
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

# Page configuration
st.set_page_config(
    page_title="Spatial Data Cleaning & Visualization Pipeline",
    page_icon="🗺️",
    layout="wide",
)

st.title("🗺️ Spatial Data Cleaning & Advanced Visualization")
st.markdown(
    "Upload raw open data or geospatial feeds to clean, validate, and inspect using interactive spatial maps and dynamic analytical dashboards."
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
    help="EPSG:27700 = British National Grid | EPSG:4326 = WGS84 (Lat/Long)",
)

st.sidebar.subheader("Visualization Settings")
map_style = st.sidebar.selectbox(
    "Map Tiles",
    options=["OpenStreetMap", "CartoDB positron", "CartoDB dark_matter"],
    index=1,
)
map_mode = st.sidebar.radio(
    "Map Display Mode",
    options=["Clustered Markers", "Density Heatmap"],
    index=0,
)

lat_col = st.sidebar.text_input("CSV Latitude Column", value="latitude")
lon_col = st.sidebar.text_input("CSV Longitude Column", value="longitude")

# --- Main App Logic ---
if uploaded_file is not None:
    try:
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

        # Run Cleaning Pipeline
        cleaned_gdf, metrics = clean_geospatial_pipeline(
            raw_gdf, target_crs=target_crs
        )

        # Top Executive Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Raw Records Ingested", f"{metrics['initial_count']:,}")
        m2.metric("Duplicates Dropped", f"{metrics['duplicates_dropped']:,}")
        m3.metric(
            "Out of Bounds Removed", f"{metrics['out_of_bounds_dropped']:,}"
        )
        m4.metric("Valid Clean Records", f"{metrics['final_count']:,}")

        st.markdown("---")

        # --- Interactive Spatial Map Section ---
        st.subheader("🗺️ Spatial Distribution & Density Analysis")

        # Reproject to WGS84 for Folium Mapping
        map_gdf = cleaned_gdf.to_crs("EPSG:4326")

        if not map_gdf.empty:
            centroid = [map_gdf.geometry.y.mean(), map_gdf.geometry.x.mean()]
            m = folium.Map(
                location=centroid, zoom_start=8, tiles=map_style, control_scale=True
            )

            # Filter out non-point geometries for point-based visualizations
            point_gdf = map_gdf[map_gdf.geometry.geom_type == "Point"]
            coords = [[point.y, point.x] for point in point_gdf.geometry]

            if map_mode == "Density Heatmap":
                HeatMap(coords, radius=12, blur=15, min_opacity=0.4).add_to(m)
            else:
                marker_cluster = MarkerCluster().add_to(m)
                # Select top 3 display columns for interactive popups
                popup_cols = [
                    c
                    for c in map_gdf.columns
                    if c not in ["geometry", lat_col, lon_col]
                ][:3]

                for idx, row in point_gdf.head(2000).iterrows():
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
                        fill_opacity=0.7,
                        popup=folium.Popup(
                            popup_html if popup_html else "Location Point",
                            max_width=250,
                        ),
                    ).add_to(marker_cluster)

            st_folium(m, width=1200, height=500)

        st.markdown("---")

        # --- Data Analytics & Dashboard Section ---
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.subheader("📊 Category Breakdown")
            # Automatically find categorical/string columns for auto-charting
            cat_cols = [
                c
                for c in cleaned_gdf.select_dtypes(include=["object"]).columns
                if c != "geometry"
            ]

            if cat_cols:
                selected_cat = st.selectbox(
                    "Select Field to Aggregate", options=cat_cols
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
                    yaxis={"categoryorder": "total ascending"}, height=350
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No text columns found for categorical aggregation.")

        with col_right:
            st.subheader("📋 Clean Data Table Preview")
            st.dataframe(
                cleaned_gdf.drop(columns="geometry", errors="ignore").head(100),
                use_container_width=True,
                height=350,
            )

        # --- Download Section ---
        st.markdown("---")
        st.subheader("💾 Export Options")
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
