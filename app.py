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

# Geographic Centroid Lookup Table mapped by Local Authority Name (`areanm`)
LA_NAME_CENTROIDS = {
    "Aberdeen City": (57.1497, -2.0943),
    "Aberdeenshire": (57.2832, -2.5714),
    "Adur": (50.8351, -0.3180),
    "Allerdale": (54.6468, -3.3598),
    "Amber Valley": (53.0450, -1.4120),
    "Angus": (56.6438, -2.8841),
    "Antrim and Newtownabbey": (54.7161, -6.2167),
    "Ards and North Down": (54.5980, -5.6961),
    "Argyll and Bute": (56.4152, -5.4710),
    "Armagh City, Banbridge and Craigavon": (54.3498, -6.6546),
    "Arun": (50.8082, -0.5539),
    "Ashfield": (53.1001, -1.2678),
    "Ashford": (51.1465, 0.8750),
    "Babergh": (52.0432, 0.8340),
    "Barking and Dagenham": (51.5607, 0.1557),
    "Barnet": (51.6252, -0.2016),
    "Barnsley": (53.5526, -1.4797),
    "Barrow-in-Furness": (54.1108, -3.2261),
    "Basildon": (51.5761, 0.4887),
    "Basingstoke and Deane": (51.2625, -1.0872),
    "Bassetlaw": (53.3338, -1.0002),
    "Bath and North East Somerset": (51.3811, -2.3590),
    "Bedford": (52.1359, -0.4667),
    "Belfast": (54.5973, -5.9301),
    "Bexley": (51.4549, 0.1505),
    "Birmingham": (52.4862, -1.8904),
    "Blaby": (52.5739, -1.1824),
    "Blackburn with Darwen": (53.7488, -2.4819),
    "Blackpool": (53.8175, -3.0515),
    "Blaenau Gwent": (51.7770, -3.1880),
    "Bolsover": (53.2301, -1.2882),
    "Bolton": (53.5769, -2.4282),
    "Boston": (52.9782, -0.0264),
    "Bournemouth, Christchurch and Poole": (50.7192, -1.8808),
    "Bracknell Forest": (51.4162, -0.7492),
    "Bradford": (53.7960, -1.7594),
    "Braintree": (51.8782, 0.5522),
    "Breckland": (52.5292, 0.8340),
    "Brent": (51.5588, -0.2817),
    "Brentwood": (51.6206, 0.3031),
    "Bridgend": (51.5072, -3.5777),
    "Brighton and Hove": (50.8225, -0.1372),
    "Broadland": (52.6821, 1.3411),
    "Bromley": (51.4039, 0.0198),
    "Bromsgrove": (52.3352, -2.0581),
    "Broxbourne": (51.7142, -0.0231),
    "Broxtowe": (52.9731, -1.2582),
    "Buckinghamshire": (51.8156, -0.8123),
    "Burnley": (53.7888, -2.2422),
    "Bury": (53.5933, -2.2966),
    "Caerphilly": (51.5780, -3.2180),
    "Calderdale": (53.7268, -1.8622),
    "Cambridge": (52.2053, 0.1218),
    "Camden": (51.5290, -0.1255),
    "Cannock Chase": (52.6892, -2.0302),
    "Canterbury": (51.2802, 1.0789),
    "Cardiff": (51.4816, -3.1791),
    "Carlisle": (54.8925, -2.9329),
    "Carmarthenshire": (51.8560, -4.3060),
    "Causeway Coast and Glens": (55.1321, -6.6661),
    "Castle Point": (51.5432, 0.5821),
    "Central Bedfordshire": (52.0012, -0.4521),
    "Ceredigion": (52.2410, -4.0620),
    "Charnwood": (52.7721, -1.2082),
    "Chelmsford": (51.7356, 0.4685),
    "Cheltenham": (51.8994, -2.0783),
    "Cherwell": (51.9282, -1.2582),
    "Cheshire East": (53.1610, -2.3182),
    "Cheshire West and Chester": (53.1905, -2.8918),
    "Chesterfield": (53.2350, -1.4210),
    "Chichester": (50.8365, -0.7792),
    "Chiltern": (51.6812, -0.6282),
    "Chorley": (53.6531, -2.6322),
    "City of Edinburgh": (55.9533, -3.1883),
    "City of London": (51.5127, -0.0918),
    "Clackmannanshire": (56.1165, -3.7520),
    "Colchester": (51.8892, 0.9042),
    "Conwy": (53.2800, -3.8300),
    "Copeland": (54.4312, -3.4210),
    "Corby": (52.4892, -0.6982),
    "Cornwall": (50.2660, -5.0527),
    "Cotswold": (51.7182, -1.9682),
    "Coventry": (52.4068, -1.5197),
    "Craven": (54.0012, -2.0821),
    "Crawley": (51.1130, -0.1831),
    "Croydon": (51.3762, -0.0982),
    "Dacorum": (51.7532, -0.4821),
    "Darlington": (54.5236, -1.5592),
    "Dartford": (51.4462, 0.2182),
    "Denbighshire": (53.1800, -3.4200),
    "Derby": (52.9225, -1.4746),
    "Derbyshire Dales": (53.1412, -1.6321),
    "Derry City and Strabane": (54.9981, -7.3093),
    "Doncaster": (53.5228, -1.1311),
    "Dover": (51.1279, 1.3134),
    "Dudley": (52.5123, -2.0811),
    "Dumfries and Galloway": (55.0700, -3.6050),
    "Dundee City": (56.4620, -2.9707),
    "Durham": (54.7761, -1.5733),
    "Ealing": (51.5130, -0.3089),
    "East Ayrshire": (55.4521, -4.2621),
    "East Cambridgeshire": (52.3982, 0.2682),
    "East Devon": (50.7382, -3.2282),
    "East Dunbartonshire": (55.9750, -4.2180),
    "East Hampshire": (51.0821, -0.9382),
    "East Hertfordshire": (51.8821, -0.0182),
    "East Lindsey": (53.2821, 0.0821),
    "East Lothian": (55.9580, -2.7820),
    "East Northamptonshire": (52.4012, -0.5282),
    "East Renfrewshire": (55.7760, -4.3310),
    "East Riding of Yorkshire": (53.8410, -0.4320),
    "East Staffordshire": (52.8312, -1.8282),
    "East Suffolk": (52.1821, 1.4282),
    "Eastbourne": (50.7680, 0.2905),
    "Eastleigh": (50.9692, -1.3531),
    "Erewash": (52.9321, -1.3382),
    "Exeter": (50.7236, -3.5275),
    "Falkirk": (56.0019, -3.7839),
    "Fareham": (50.8542, -1.1782),
    "Fenland": (52.5682, 0.0482),
    "Fermanagh and Omagh": (54.3461, -7.6381),
    "Fife": (56.2082, -3.1495),
    "Flintshire": (53.2200, -3.1400),
    "Folkestone and Hythe": (51.0812, 1.1682),
    "Forest of Dean": (51.8082, -2.5282),
    "Fylde": (53.7821, -2.9282),
    "Gateshead": (54.9531, -1.6033),
    "Gedling": (53.0012, -1.1082),
    "Glasgow City": (55.8642, -4.2518),
    "Gloucester": (51.8642, -2.2381),
    "Gosport": (50.7952, -1.1282),
    "Gravesham": (51.4412, 0.3682),
    "Great Yarmouth": (52.6083, 1.7305),
    "Greenwich": (51.4892, 0.0072),
    "Guildford": (51.2362, -0.5704),
    "Gwynedd": (52.8400, -3.8300),
    "Hackney": (51.5450, -0.0553),
    "Halton": (53.3421, -2.7312),
    "Hambleton": (54.3382, -1.4282),
    "Hammersmith and Fulham": (51.4927, -0.2339),
    "Harborough": (52.4812, -0.9282),
    "Haringey": (51.5906, -0.1110),
    "Harlow": (51.7712, 0.1021),
    "Harrogate": (53.9921, -1.5372),
    "Harrow": (51.5806, -0.3420),
    "Hart": (51.2782, -0.8582),
    "Hartlepool": (54.6860, -1.2130),
    "Hastings": (50.8552, 0.5722),
    "Havant": (50.8521, -0.9821),
    "Havering": (51.5812, 0.1837),
    "Herefordshire": (52.0564, -2.7160),
    "Hertsmere": (51.6582, -0.2782),
    "High Peak": (53.3282, -1.8782),
    "Highland": (57.4778, -4.2247),
    "Hillingdon": (51.5441, -0.4760),
    "Hinckley and Bosworth": (52.5412, -1.3782),
    "Horsham": (51.0621, -0.3282),
    "Hounslow": (51.4746, -0.3680),
    "Huntingdonshire": (52.3321, -0.1821),
    "Inverclyde": (55.9480, -4.7580),
    "Ipswich": (52.0567, 1.1482),
    "Isle of Anglesey": (53.2600, -4.3300),
    "Isle of Wight": (50.6938, -1.3047),
    "Islington": (51.5416, -0.1022),
    "Kensington and Chelsea": (51.5020, -0.1947),
    "Kent": (51.2787, 0.5217),
    "Kingston upon Hull": (53.7676, -0.3274),
    "Kingston upon Thames": (51.4085, -0.3064),
    "Kirklees": (53.6458, -1.7850),
    "Knowsley": (53.4412, -2.8312),
    "Lambeth": (51.4607, -0.1163),
    "Lancaster": (54.0466, -2.8007),
    "Leeds": (53.8008, -1.5491),
    "Leicester": (52.6369, -1.1398),
    "Lewisham": (51.4452, -0.0209),
    "Lichfield": (52.6835, -1.8265),
    "Lincoln": (53.2307, -0.5406),
    "Lisburn and Castlereagh": (54.5121, -6.0421),
    "Liverpool": (53.4084, -2.9916),
    "Luton": (51.8787, -0.4200),
    "Maidstone": (51.2720, 0.5290),
    "Maldon": (51.7312, 0.6782),
    "Malvern Hills": (52.1121, -2.3282),
    "Manchester": (53.4808, -2.2426),
    "Mansfield": (53.1462, -1.1982),
    "Medway": (51.3799, 0.5422),
    "Melton": (52.7621, -0.8882),
    "Mendip": (51.1821, -2.5282),
    "Merthyr Tydfil": (51.7480, -3.3780),
    "Merton": (51.4014, -0.1958),
    "Mid and East Antrim": (54.8631, -6.2781),
    "Mid Ulster": (54.6421, -6.6821),
    "Mid Devon": (50.9082, -3.4882),
    "Mid Sussex": (51.0121, -0.1382),
    "Middlesbrough": (54.5742, -1.2350),
    "Midlothian": (55.8920, -3.0680),
    "Milton Keynes": (52.0406, -0.7594),
    "Mole Valley": (51.2321, -0.3382),
    "Monmouthshire": (51.7800, -2.9200),
    "Moray": (57.6490, -3.3180),
    "Neath Port Talbot": (51.6600, -3.8000),
    "New Forest": (50.8121, -1.5821),
    "Newark and Sherwood": (53.0782, -0.8082),
    "Newcastle under Lyme": (53.0112, -2.2282),
    "Newcastle upon Tyne": (54.9783, -1.6178),
    "Newham": (51.5077, 0.0469),
    "Newry, Mourne and Down": (54.1781, -6.3381),
    "Newport": (51.5842, -2.9977),
    "North Ayrshire": (55.6140, -4.6710),
    "North Devon": (51.0821, -4.0582),
    "North East Derbyshire": (53.1821, -1.4282),
    "North East Lincolnshire": (53.5592, -0.0682),
    "North Hertfordshire": (51.9482, -0.2782),
    "North Kesteven": (53.0782, -0.5482),
    "North Lanarkshire": (55.8650, -3.9620),
    "North Lincolnshire": (53.5821, -0.6482),
    "North Norfolk": (52.8821, 1.1821),
    "North Northamptonshire": (52.4000, -0.7000),
    "North Somerset": (51.3821, -2.8282),
    "North Tyneside": (55.0121, -1.4882),
    "North Warwickshire": (52.5782, -1.6282),
    "North West Leicestershire": (52.7482, -1.3782),
    "North Northamptonshire": (52.3800, -0.7000),
    "North Tyneside": (55.0162, -1.4821),
    "Northumberland": (55.1950, -1.6800),
    "Norwich": (52.6309, 1.2974),
    "Nottingham": (52.9548, -1.1581),
    "Nuneaton and Bedworth": (52.5232, -1.4682),
    "Oadby and Wigston": (52.5882, -1.0882),
    "Oldham": (53.5409, -2.1114),
    "Orkney Islands": (58.9814, -2.9600),
    "Oxford": (51.7520, -1.2577),
    "Pembroke": (51.6700, -4.9100),
    "Pembrokeshire": (51.8000, -4.9700),
    "Pendle": (53.8582, -2.1682),
    "Perth and Kinross": (56.3960, -3.4320),
    "Peterborough": (52.5695, -0.2405),
    "Plymouth": (50.3755, -4.1427),
    "Portsmouth": (50.8198, -1.0880),
    "Powys": (52.3000, -3.4000),
    "Preston": (53.7632, -2.7031),
    "Reading": (51.4543, -0.9781),
    "Redcar and Cleveland": (54.5982, -1.0782),
    "Redbridge": (51.5806, 0.0882),
    "Redditch": (52.3062, -1.9482),
    "Reigate and Banstead": (51.2382, -0.1982),
    "Renfrewshire": (55.8460, -4.4230),
    "Rhondda Cynon Taf": (51.6000, -3.4300),
    "Ribble Valley": (53.8721, -2.3882),
    "Richmond upon Thames": (51.4470, -0.3260),
    "Richmondshire": (54.4012, -1.7382),
    "Rochdale": (53.6158, -2.1568),
    "Rochford": (51.5821, 0.7082),
    "Rossendale": (53.7012, -2.2882),
    "Rother": (50.9482, 0.4682),
    "Rotherham": (53.4300, -1.3570),
    "Rugby": (52.3708, -1.2650),
    "Runnymede": (51.3721, -0.5482),
    "Rushcliffe": (52.9282, -1.0882),
    "Rushmoor": (51.2782, -0.7582),
    "Rutland": (52.6682, -0.6382),
    "Ryedale": (54.1382, -0.7882),
    "Salford": (53.4875, -2.2901),
    "Salford": (53.4830, -2.2931),
    "Sandwell": (52.5282, -2.0182),
    "Scarborough": (54.2821, -0.4082),
    "Scottish Borders": (55.6020, -2.7820),
    "Sedgemoor": (51.1282, -2.9982),
    "Sefton": (53.5282, -3.0082),
    "Selby": (53.7821, -1.0682),
    "Sevenoaks": (51.2782, 0.1882),
    "Sheffield": (53.3811, -1.4701),
    "Shetland Islands": (60.1530, -1.1493),
    "Shropshire": (52.7073, -2.7533),
    "Slough": (51.5105, -0.5950),
    "Solihull": (52.4128, -1.7781),
    "Somerset West and Taunton": (51.0182, -3.1082),
    "South Ayrshire": (55.4580, -4.6290),
    "South Cambridgeshire": (52.1821, 0.1282),
    "South Derbyshire": (52.8282, -1.5482),
    "South Gloucestershire": (51.5382, -2.4482),
    "South Hams": (50.3821, -3.7882),
    "South Holland": (52.7882, -0.1482),
    "South Kesteven": (52.9182, -0.6382),
    "South Lakeland": (54.3282, -2.7482),
    "South Lanarkshire": (55.6730, -3.7820),
    "South Norfolk": (52.5282, 1.2282),
    "South Northamptonshire": (52.1282, -1.0282),
    "South Oxfordshire": (51.6282, -1.0882),
    "South Ribble": (53.7182, -2.7082),
    "South Somerset": (50.9482, -2.6382),
    "South Staffordshire": (52.6282, -2.1882),
    "South Tyneside": (54.9782, -1.4282),
    "South hams": (50.3821, -3.7882),
    "Southampton": (50.9097, -1.4044),
    "Southend-on-Sea": (51.5459, 0.7077),
    "Southwark": (51.5035, -0.0804),
    "Spelthorne": (51.4321, -0.4882),
    "St Albans": (51.7527, -0.3394),
    "St. Helens": (53.4542, -2.7350),
    "Stafford": (52.8072, -2.1172),
    "Staffordshire Moorlands": (53.1082, -1.9882),
    "Stevenage": (51.9017, -0.2019),
    "Stirling": (56.1165, -3.9369),
    "Stockport": (53.4106, -2.1575),
    "Stockton-on-Tees": (54.5683, -1.3175),
    "Stoke-on-Trent": (53.0027, -2.1794),
    "Stratford-on-Avon": (52.1912, -1.7082),
    "Stroud": (51.7482, -2.2182),
    "Sunderland": (54.9069, -1.3811),
    "Surrey Heath": (51.3382, -0.7082),
    "Sutton": (51.3618, -0.1945),
    "Swale": (51.3382, 0.7282),
    "Swansea": (51.6214, -3.9436),
    "Swindon": (51.5558, -1.7797),
    "Tameside": (53.4800, -2.0800),
    "Tamworth": (52.6338, -1.6959),
    "Tandridge": (51.2582, -0.0282),
    "Teignbridge": (50.5382, -3.6082),
    "Telford and Wrekin": (52.6782, -2.4482),
    "Tendring": (51.8382, 1.1582),
    "Test Valley": (51.1382, -1.4882),
    "Tewkesbury": (51.9882, -2.1582),
    "Thanet": (51.3821, 1.3821),
    "Three Rivers": (51.6382, -0.4682),
    "Thurrock": (51.5078, 0.3578),
    "Tonbridge and Malling": (51.2882, 0.3282),
    "Torbay": (50.4619, -3.5253),
    "Torfaen": (51.7000, -3.0300),
    "Torridge": (50.9821, -4.1582),
    "Tower Hamlets": (51.5099, -0.0059),
    "Trafford": (53.4400, -2.3000),
    "Tunbridge Wells": (51.1321, 0.2632),
    "Vale of Glamorgan": (51.4000, -3.3500),
    "Vale of White Horse": (51.6182, -1.4882),
    "Wakefield": (53.6833, -1.4977),
    "Walsall": (52.5862, -1.9829),
    "Waltham Forest": (51.5908, -0.0134),
    "Wandsworth": (51.4567, -0.1910),
    "Warrington": (53.3900, -2.5900),
    "Warwick": (52.2820, -1.5820),
    "Watford": (51.6565, -0.3903),
    "Waverley": (51.1821, -0.6182),
    "Wealden": (50.9821, 0.2082),
    "Welwyn Hatfield": (51.7682, -0.2182),
    "West Dunbartonshire": (55.9520, -4.5640),
    "West Devon": (50.6182, -4.0882),
    "West Lancashire": (53.5682, -2.8882),
    "West Lindsey": (53.3882, -0.6382),
    "West Lothian": (55.8860, -3.5320),
    "West Northamptonshire": (52.2400, -0.9000),
    "West Oxfordshire": (51.8182, -1.4882),
    "West Suffolk": (52.2482, 0.7182),
    "West Berkshire": (51.4010, -1.3230),
    "Westminster": (51.4975, -0.1357),
    "Wigan": (53.5448, -2.6318),
    "Wiltshire": (51.3490, -1.9100),
    "Winchester": (51.0632, -1.3080),
    "Windsor and Maidenhead": (51.5217, -0.6042),
    "Wirral": (53.3800, -3.0500),
    "Woking": (51.3168, -0.5600),
    "Wokingham": (51.4100, -0.8330),
    "Wolverhampton": (52.5862, -2.1288),
    "Worcester": (52.1920, -2.2200),
    "Worthing": (50.8179, -0.3729),
    "Wychavon": (52.1182, -2.0882),
    "Wycombe": (51.6282, -0.7482),
    "Wyre": (53.8821, -2.8882),
    "Wyre Forest": (52.3882, -2.2882),
    "Wrexham": (53.0460, -2.9930),
    "York": (53.9591, -1.0815),
}

# Aggregate entries to filter out
AGGREGATE_ENTRIES = {
    "United Kingdom", "England", "Scotland", "Wales", "Northern Ireland",
    "North East", "North West", "Yorkshire and The Humber", "East Midlands",
    "West Midlands", "East of England", "London", "South East", "South West",
    "Great Britain"
}

@st.cache_data
def load_dataset(url: str) -> pd.DataFrame:
    return pd.read_csv(url)

# --- Header ---
st.title("⚡ ONS Public Electric Vehicle Chargers: Local Authorities")
st.caption("Source: Office for National Statistics (ONS) / Department for Transport (DfT) Explore Local Statistics Indicator")

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

    # Detect local authority name column
    areanm_col = next(
        (c for c in df_raw.columns if c.lower() in ["areanm", "ladnm", "local_authority_name", "region", "areacd"]),
        None
    )

    if areanm_col:
        # Filter out national/regional aggregates
        raw_unique = df_raw[areanm_col].dropna().unique()
        la_options = sorted([name for name in raw_unique if str(name).strip() not in AGGREGATE_ENTRIES])

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
            help="Select a local authority to update the metrics and center the map on that council."
        )

        filtered_df = df_raw[df_raw[areanm_col] == selected_la].copy()
    else:
        selected_la = "All Local Authorities"
        filtered_df = df_raw.copy()

    # Detect existing latitude/longitude OR apply name centroid lookup
    cols_lower = {col.lower(): col for col in filtered_df.columns}
    found_lat = next((cols_lower[c] for c in ["latitude", "lat", "y"] if c in cols_lower), None)
    found_lon = next((cols_lower[c] for c in ["longitude", "long", "lon", "x"] if c in cols_lower), None)
    code_col = next((cols_lower[c] for c in ["areacd", "ladcd", "area_code", "gss_code", "lad23cd"] if c in cols_lower), None)

    if found_lat and found_lon:
        filtered_df[found_lat] = pd.to_numeric(filtered_df[found_lat], errors="coerce")
        filtered_df[found_lon] = pd.to_numeric(filtered_df[found_lon], errors="coerce")
        filtered_df = filtered_df.dropna(subset=[found_lat, found_lon])
        gdf = gpd.GeoDataFrame(
            filtered_df,
            geometry=gpd.points_from_xy(filtered_df[found_lon], filtered_df[found_lat]),
            crs="EPSG:4326"
        )
    else:
        # Map latitude/longitude dynamically using the selected Local Authority Name (`areanm`)
        lat_val, lon_val = LA_NAME_CENTROIDS.get(str(selected_la).strip(), (52.5000, -1.5000))
        filtered_df["latitude"] = lat_val
        filtered_df["longitude"] = lon_val
        gdf = gpd.GeoDataFrame(
            filtered_df,
            geometry=gpd.points_from_xy(filtered_df["longitude"], filtered_df["latitude"]),
            crs="EPSG:4326"
        )

    # --- KPI Summary ---
    st.markdown(f"### 📊 Local Authority Summary: **{selected_la}**")
    m1, m2, m3, m4 = st.columns(4)
    
    m1.metric("Local Authority (`areanm`)", str(selected_la))
    
    gss_val = gdf[code_col].iloc[0] if code_col and not gdf.empty else "N/A"
    m2.metric("Council Area Code (`areacd`)", str(gss_val))
    
    period_col = next((cols_lower[c] for c in ["period", "year"] if c in cols_lower), None)
    period_val = gdf[period_col].iloc[0] if period_col and not gdf.empty else "Latest"
    m3.metric("Time Period (`period`)", str(period_val))
    
    val_col = next((cols_lower[c] for c in ["value", "chargers"] if c in cols_lower), None)
    if val_col:
        m4.metric("EV Charger Metric (`value`)", f"{gdf[val_col].sum():,.1f}")
    else:
        m4.metric("Mapped Records", f"{len(gdf):,}")

    st.markdown("---")

    # --- Interactive Map & Data Table ---
    col_map, col_table = st.columns([3, 2])

    with col_map:
        st.subheader(f"🗺️ Spatial Centroid Map for {selected_la}")

        if not gdf.empty:
            lat_mean = float(gdf.geometry.y.mean())
            lon_mean = float(gdf.geometry.x.mean())

            m = folium.Map(
                location=[lat_mean, lon_mean],
                zoom_start=11,
                tiles=map_style,
                control_scale=True
            )

            coords = [[p.y, p.x] for p in gdf.geometry]

            if map_mode == "Density Heatmap":
                HeatMap(coords, radius=18, blur=15, min_opacity=0.4).add_to(m)
            else:
                marker_cluster = MarkerCluster().add_to(m)
                for idx, row in gdf.head(1000).iterrows():
                    popup_html = "<div style='font-family: sans-serif; font-size: 12px;'>"
                    popup_html += f"<b>Local Authority (areanm):</b> {selected_la}<br>"
                    if code_col:
                        popup_html += f"<b>Area Code (areacd):</b> {row[code_col]}<br>"
                    if period_col:
                        popup_html += f"<b>Time Period (period):</b> {row[period_col]}<br>"
                    if val_col:
                        popup_html += f"<b>Charger Metric (value):</b> {row[val_col]}<br>"
                    popup_html += "</div>"

                    folium.CircleMarker(
                        location=[row.geometry.y, row.geometry.x],
                        radius=8,
                        color="#005A9C",
                        fill=True,
                        fill_color="#0080FF",
                        fill_opacity=0.8,
                        popup=folium.Popup(popup_html, max_width=250)
                    ).add_to(marker_cluster)

            st_folium(
                m,
                use_container_width=True,
                height=480,
                key=f"map_render_{selected_la}"
            )

    with col_table:
        st.subheader("📋 Local Authority Data Table")

        display_df = gdf.drop(columns=["geometry", "latitude", "longitude"], errors="ignore")
        st.dataframe(
            display_df,
            use_container_width=True,
            height=360
        )

        geojson_bytes = gdf.to_crs("EPSG:4326").to_json()
        st.download_button(
            label=f"📥 Export {selected_la} GeoJSON",
            data=geojson_bytes,
            file_name=f"{str(selected_la).lower().replace(' ', '_')}_la_data.geojson",
            mime="application/geo+json",
            use_container_width=True
        )

except Exception as e:
    st.error(f"App Execution Error: {str(e)}")
