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
    page_title="ONS Spatial Data Cleaner & Visualiser",
    page_icon="🗺️",
    layout="wide",
)

st.title("🗺️ ONS Spatial Data Cleaner & Visualiser")
st.markdown(
    "Upload ONS Local Authority datasets, EV charging statistics, or geospatial feeds to validate area codes, clean spatial coordinates, and generate analytical dashboards."
)

# --- Sample Dataset Definition ---
SAMPLE_CSV_DATA = """LADCD,LADNM,LADNMW,region,latitude,longitude
W06000024,Merthyr Tydfil,Merthyr Tudful,Wales,51.7480,-3.3780
E06000001,Hartlepool,,North East,54.6860,-1.2130
E08000025,Birmingham,,West Midlands,52.4862,-1.8904
E08000035,Leeds,,Yorkshire and The Humber,53.8008,-1.5491
S12000033,Aberdeen City,,Scotland,57.1497,-2.0943
E09000001,City of London,,London,51.5127,-0.0918
S12000034,Aberdeenshire,,Scotland,57.2832,-2.5714
E07000223,Adur,,South East,50.8351,-0.3180
"""


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

    # 5. Normalize Text Fields (Format area codes and clean strings)
    for col in df_clean.select_dtypes(include=["object"]).columns:
        if col != "geometry":
            # Keep GSS 9-character area codes (e.g., W06000024) in uppercase
            if col.upper() in ["LADCD", "AREA_CODE", "GSS_CODE", "LAD23CD"]:
                df_clean[col] = df_clean[col].astype(str).str.strip().str.upper()
            else:
                df_clean[col] = (
                    df_clean[col].astype(str).str.strip().str.lower().str.title()
                )

    metrics["final_count"] = len(df_clean)
    return df_clean, metrics


# --- Sidebar Setup ---
st.sidebar.header("1. Data Ingestion")
uploaded_file = st.sidebar.file_uploader(
    "Upload Dataset", type=["geojson", "csv", "gpkg", "json"]
)

st.sidebar.download_button(
    label="📥 Download Sample ONS CSV",
    data=SAMPLE_CSV_DATA,
    file_name="ons_sample_local_authorities.csv",
    mime="text/csv",
    help="Download a clean test dataset containing standard ONS codes (e.g. W06000024) and coordinates.",
)

st.sidebar.markdown("---")
st.sidebar.header("2. Pipeline Settings")
target_crs = st.sidebar.selectbox(
    "Target CRS",
    options=["EPSG:27700", "EPSG:4326"],
    index=0,
    help="EPSG:27700 = British National Grid (Metres) | EPSG:4326 = WGS84 (Lat/Long)",
)

st.sidebar.subheader("Map Visualisation")
map_style = st.sidebar.selectbox(
    "Map Style",
    options=["OpenStreetMap", "CartoDB positron", "CartoDB dark_matter"],
    index=1,
)
map_mode = st.sidebar.radio(
    "Display Mode",
    options=["Clustered Markers", "Density Heatmap"],
    index=0,
)

# --- Main Logic ---
if uploaded_file is not None:
    try:
        file_ext = uploaded_file.name.split(".")[-1].lower()

        if file_ext == "csv":
            df_raw = pd.read_csv(uploaded_file)

            # Flexible Auto-Detection for Coordinate Headers
            cols_lower = {col.lower(): col for col in df_raw.columns}
            found_lat = next(
                (cols_lower[c] for c in ["latitude", "lat", "y_coord", "y"] if c in cols_lower),
                None,
            )
            found_lon = next(
                (cols_lower[c] for c in ["longitude", "long", "lng", "lon", "x_coord", "x"] if c in cols_lower),
                None,
            )

            if found_lat and found_lon:
                df_raw[found_lat] = pd.to_numeric(df_raw[found_lat], errors="coerce")
                df_raw[found_lon] = pd.to_numeric(df_raw[found_lon], errors="coerce")
                df_raw = df_raw.dropna(subset=[found_lat, found_lon])

                raw_gdf = gpd.GeoDataFrame(
                    df_raw,
                    geometry=gpd.points_from_xy(df_raw[found_lon], df_raw[found_lat]),
                    crs="EPSG:4326",
                )
            else:
                st.error(
                    f"Could not automatically detect spatial coordinate columns. Found headers: `{list(df_raw.columns)}`. Please ensure your file contains latitude/longitude or download the sample dataset in the sidebar."
                )
                st.stop()
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            raw_gdf = gpd.read_file(tmp_path)

        # Run Pipeline
        cleaned_gdf, metrics = clean_geospatial_pipeline(raw_gdf, target_crs=target_crs)

        # Metrics Display
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Raw Records Ingested", f"{metrics['initial_count']:,}")
        m2.metric("Duplicates Removed", f"{metrics['duplicates_dropped']:,}")
        m3.metric("Out of Bounds Removed", f"{metrics['out_of_bounds_dropped']:,}")
        m4.metric("Valid Clean Records", f"{metrics['final_count']:,}")

        st.markdown("---")

        # Map Visualisation
        st.subheader("🗺️ Regional Distribution Map")
        map_gdf = cleaned_gdf.to_crs("EPSG:4326")

        if not map_gdf.empty:
            centroid = [map_gdf.geometry.y.mean(), map_gdf.geometry.x.mean()]
            m = folium.Map(location=centroid, zoom_start=7, tiles=map_style, control_scale=True)

            point_gdf = map_gdf[map_gdf.geometry.geom_type == "Point"]
            coords = [[point.y, point.x] for point in point_gdf.geometry]

            if map_mode == "Density Heatmap":
                HeatMap(coords, radius=12, blur=15, min_opacity=0.4).add_to(m)
            else:
                marker_cluster = MarkerCluster().add_to(m)
                popup_cols = [c for c in map_gdf.columns if c not in ["geometry"]][:4]

                for idx, row in point_gdf.head(2000).iterrows():
                    popup_html = "<br>".join([f"<b>{col}:</b> {row[col]}" for col in popup_cols])
                    folium.CircleMarker(
                        location=[row.geometry.y, row.geometry.x],
                        radius=6,
                        color="#005A9C",
                        fill=True,
                        fill_color="#0080FF",
                        fill_opacity=0.8,
                        popup=folium.Popup(popup_html, max_width=300),
                    ).add_to(marker_cluster)

            st_folium(m, width=1200, height=480)

        st.markdown("---")

        # Analytics Dashboard
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.subheader("📊 Attribute Aggregation")
            cat_cols = [c for c in cleaned_gdf.select_dtypes(include=["object"]).columns if c != "geometry"]

            if cat_cols:
                selected_cat = st.selectbox("Group By Field", options=cat_cols)
                counts = cleaned_gdf[selected_cat].value_counts().head(10).reset_index()
                counts.columns = [selected_cat, "Count"]

                fig = px.bar(
                    counts,
                    x="Count",
                    y=selected_cat,
                    orientation="h",
                    title=f"Top Records by '{selected_cat}'",
                    color="Count",
                    color_continuous_scale="Blues",
                )
                fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=350)
                st.plotly_chart(fig, use_container_width=True)

        with col_right:
            st.subheader("📋 Data Table Preview")
            st.dataframe(
                cleaned_gdf.drop(columns="geometry", errors="ignore").head(100),
                use_container_width=True,
                height=350,
            )

        # Downloads
        st.markdown("---")
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
    st.info("👈 Upload a spatial file or click 'Download Sample ONS CSV' in the sidebar to test the pipeline.")
