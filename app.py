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

