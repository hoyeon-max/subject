
import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import html
import re
from datetime import datetime, date, timedelta, timezone
from urllib.parse import quote

# =========================================================
# WORLD DISASTER LIVE
# =========================================================

st.set_page_config(
    page_title="WORLD DISASTER LIVE",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

UTC = timezone.utc
NOW = datetime.now(UTC)
TODAY_UTC = NOW.date()

HAZARDS = [
    "All", "Typhoon", "Earthquake", "Wildfire", "Flood",
    "Heavy Rain", "Drought", "Heavy Snow", "Heatwave",
    "Cold Wave", "Landslide",
]

HAZARD_LABELS = {
    "All": "🌐 All Disasters",
    "Typhoon": "🌀 Typhoon",
    "Earthquake": "🌎 Earthquake",
    "Wildfire": "🔥 Wildfire",
    "Flood": "🌊 Flood",
    "Heavy Rain": "🌧️ Heavy Rain",
    "Drought": "☀️ Drought",
    "Heavy Snow": "❄️ Heavy Snow",
    "Heatwave": "🌡️ Heatwave",
    "Cold Wave": "🥶 Cold Wave",
    "Landslide": "⛰️ Landslide",
}

# 공식 기관의 정보 확인 페이지
OFFICIAL_SOURCES = {
    "Global": {
        "GDACS": "https://www.gdacs.org/",
        "UNDRR": "https://www.undrr.org/",
        "ReliefWeb": "https://reliefweb.int/",
    },
    "Earthquake": {
        "USGS Earthquake Map": "https://earthquake.usgs.gov/earthquakes/map/",
        "USGS Earthquake Data": "https://earthquake.usgs.gov/fdsnws/event/1/",
    },
    "Typhoon": {
        "NOAA / NHC": "https://www.nhc.noaa.gov/",
        "JTWC": "https://www.metoc.navy.mil/jtwc/jtwc.html",
        "GDACS": "https://www.gdacs.org/",
    },
    "Wildfire": {
        "NASA FIRMS": "https://firms.modaps.eosdis.nasa.gov/",
        "Copernicus EMS": "https://emergency.copernicus.eu/",
    },
    "Flood": {
        "Copernicus EMS": "https://emergency.copernicus.eu/",
        "GDACS": "https://www.gdacs.org/",
    },
    "Heavy Rain": {
        "WMO": "https://wmo.int/",
        "GDACS": "https://www.gdacs.org/",
    },
    "Drought": {
        "WMO": "https://wmo.int/",
        "UNDRR": "https://www.undrr.org/",
    },
    "Heavy Snow": {
        "WMO": "https://wmo.int/",
        "GDACS": "https://www.gdacs.org/",
    },
    "Heatwave": {
        "WMO": "https://wmo.int/",
        "WHO": "https://www.who.int/health-topics/heatwaves",
    },
    "Cold Wave": {
        "WMO": "https://wmo.int/",
        "WHO": "https://www.who.int/",
    },
    "Landslide": {
        "USGS Landslides": "https://www.usgs.gov/programs/landslide-hazards",
        "GDACS": "https://www.gdacs.org/",
    },
    "South Korea": {
        "Ministry of the Interior and Safety": "https://www.mois.go.kr/",
        "Korea Meteorological Administration": "https://www.kma.go.kr/",
        "Public Data Portal": "https://www.data.go.kr/",
    },
}

GDACS_RSS = "https://www.gdacs.org/xml/rss.xml"
USGS_API = "https://earthquake.usgs.gov/fdsnws/event/1/query"

# =========================================================
# STYLE
# =========================================================

st.markdown("""
<style>
.stApp {
    background: #0f172a;
    color: #e5e7eb;
}
header[data-testid="stHeader"] {
    background: #0f172a;
}
.block-container {
    max-width: 1500px;
    padding-top: 1.3rem;
    padding-bottom: 3rem;
}
h1, h2, h3, h4, p, label, span {
    color: #e5e7eb;
}
[data-testid="stMetric"] {
    background: #172238;
    border: 1px solid #2a3a55;
    border-radius: 12px;
    padding: 16px;
}
.disaster-card {
    background: #172238;
    border: 1px solid #2a3a55;
    border-radius: 14px;
    padding: 18px;
    margin-bottom: 10px;
    min-height: 200px;
}
.disaster-title {
    font-size: 19px;
    font-weight: 700;
    line-height: 1.45;
    margin-bottom: 10px;
}
.disaster-meta {
    font-size: 13px;
    color: #aab9ce;
    margin: 5px 0;
}
.tag {
    display: inline-block;
    background: #263750;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
    margin-bottom: 10px;
}
.source-box {
    background: #172238;
    border: 1px solid #2a3a55;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 10px;
}
div.stButton > button {
    border-radius: 8px;
    min-height: 40px;
    border: 1px solid #334766;
}
a {
    color: #7dd3fc !important;
}
hr {
    border-color: #2a3a55;
}
.small-muted {
    color: #94a3b8;
    font-size: 12px;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# UTILITIES
# =========================================================

def parse_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except (ValueError, TypeError):
        return None


def classify_hazard(text):
    text = (text or "").lower()

    patterns = [
        ("Earthquake", ["earthquake", "seismic"]),
        ("Typhoon", [
            "tropical cyclone", "typhoon", "hurricane",
            "cyclone", "tropical storm"
        ]),
        ("Wildfire", ["wildfire", "wild fire", "forest fire"]),
        ("Flood", ["flood", "flash flood"]),
        ("Heavy Rain", ["heavy rain", "extreme rainfall", "rainfall"]),
        ("Drought", ["drought"]),
        ("Heavy Snow", ["heavy snow", "snowstorm", "blizzard"]),
        ("Heatwave", ["heatwave", "heat wave", "extreme heat"]),
        ("Cold Wave", ["cold wave", "cold spell", "extreme cold"]),
        ("Landslide", ["landslide", "mudslide"]),
    ]

    for hazard, keywords in patterns:
        if any(keyword in text for keyword in keywords):
            return hazard

    return "Other"


def event_id(source, external_id):
    return f"{source}:{external_id}"


def official_sources_for(hazard):
    names = ["GDACS", "UNDRR", "ReliefWeb"]

    if hazard in OFFICIAL_SOURCES:
        names = list(OFFICIAL_SOURCES[hazard].keys()) + names

    result = {}
    for name in names:
        url = None
        for group in OFFICIAL_SOURCES.values():
            if name in group:
                url = group[name]
                break
        if url:
            result[name] = url

    # Preserve order and remove duplicate names
    return result


# =========================================================
# DATA SOURCES
# =========================================================

@st.cache_data(ttl=300, show_spinner=False)
def fetch_usgs(start_date, end_date):
    """USGS earthquake observations. No API key required."""
    params = {
        "format": "geojson",
        "starttime": start_date.isoformat(),
        "endtime": (end_date + timedelta(days=1)).isoformat(),
        "orderby": "time",
        "limit": 500,
    }

    response = requests.get(
        USGS_API,
        params=params,
        timeout=25,
        headers={"User-Agent": "WorldDisasterLive/1.0"},
    )
    response.raise_for_status()
    payload = response.json()

    events = []

    for item in payload.get("features", []):
        properties = item.get("properties", {}) or {}
        geometry = item.get("geometry", {}) or {}
        coords = geometry.get("coordinates", [])

        timestamp = properties.get("time")
        if timestamp is None:
            continue

        occurred = datetime.fromtimestamp(timestamp / 1000, tz=UTC)
        if not (start_date <= occurred.date() <= end_date):
            continue

        magnitude = properties.get("mag")
        place = properties.get("place") or "Location not specified"
        external_id = item.get("id", str(timestamp))

        events.append({
            "id": event_id("USGS", external_id),
            "title": f"Earthquake — {place}",
            "hazard": "Earthquake",
            "location": place,
            "occurred": occurred,
            "source": "USGS",
            "source_url": properties.get("url")
                or "https://earthquake.usgs.gov/earthquakes/map/",
            "official_url": "https://earthquake.usgs.gov/earthquakes/map/",
            "description": properties.get("title") or "USGS earthquake observation.",
            "magnitude": magnitude,
            "latitude": coords[1] if len(coords) >= 2 else None,
            "longitude": coords[0] if len(coords) >= 2 else None,
            "status": "Observation",
            "deaths": None,
            "missing": None,
            "damage": None,
            "data_note": (
                "USGS earthquake observations do not provide a complete "
                "global count of deaths, missing persons, or property damage."
            ),
        })

    return events


@st.cache_data(ttl=300, show_spinner=False)
def fetch_gdacs(start_date, end_date):
    """GDACS public RSS feed. Data availability depends on the feed."""
    response = requests.get(
        GDACS_RSS,
        timeout=25,
        headers={"User-Agent": "WorldDisasterLive/1.0"},
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)
    events = []

    for item in root.findall(".//item"):
        title = item.findtext("title", default="Disaster alert")
        link = item.findtext("link", default="https://www.gdacs.org/")
        description = item.findtext("description", default="")
        pub_date = item.findtext("pubDate", default="")
        guid = item.findtext("guid", default=link)

        occurred = None
        if pub_date:
            try:
                occurred = datetime.strptime(
                    pub_date.strip(), "%a, %d %b %Y %H:%M:%S %Z"
                ).replace(tzinfo=UTC)
            except ValueError:
                try:
                    occurred = datetime.strptime(
                        pub_date.strip(), "%a, %d %b %Y %H:%M:%S %z"
                    ).astimezone(UTC)
                except ValueError:
                    occurred = None

        # If publication date cannot be parsed, do not pretend it matches
        # the requested time window.
        if occurred is None:
            continue

        if not (start_date <= occurred.date() <= end_date):
            continue

        combined_text = f"{title} {description}"
        hazard = classify_hazard(combined_text)
        if hazard == "Other":
            continue

        clean_description = re.sub(
            r"<[^>]+>", " ", description
        )
        clean_description = html.unescape(clean_description)
        clean_description = re.sub(r"\s+", " ", clean_description).strip()

        events.append({
            "id": event_id("GDACS", guid),
            "title": html.unescape(title),
            "hazard": hazard,
            "location": "See official GDACS alert",
            "occurred": occurred,
            "source": "GDACS",
            "source_url": link if link.startswith("https://") else "https://www.gdacs.org/",
            "official_url": "https://www.gdacs.org/",
            "description": clean_description or "See the original GDACS alert.",
            "magnitude": None,
            "latitude": None,
            "longitude": None,
            "status": "Alert",
            "deaths": None,
            "missing": None,
            "damage": None,
            "data_note": (
                "The RSS alert is not a standardized official casualty or "
                "property-damage record. Check the original alert and "
                "the affected country's official reports."
            ),
        })

    return events


def load_events(start_date, end_date):
    events = []
    errors = []

    try:
        events.extend(fetch_usgs(start_date, end_date))
    except Exception as exc:
        errors.append(f"USGS: {exc}")

    try:
        events.extend(fetch_gdacs(start_date, end_date))
    except Exception as exc:
        errors.append(f"GDACS: {exc}")

    # Avoid duplicate records from the same source.
    unique = {}
    for event in events:
        unique[event["id"]] = event

    return list(unique.values()), errors


# =========================================================
# HEADER AND UTC CLOCK
# =========================================================

left, center, right = st.columns([2, 3, 2])

with left:
    st.markdown(
        "<div style='font-size:12px;color:#94a3b8;letter-spacing:2px'>"
        "GLOBAL HAZARD MONITOR</div>",
        unsafe_allow_html=True,
    )

with center:
    st.markdown(
        "<div style='text-align:center;font-size:30px;font-weight:800;"
        "letter-spacing:2px'>🌍 WORLD DISASTER LIVE</div>",
        unsafe_allow_html=True,
    )

with right:
    st.markdown(
        f"<div style='text-align:right;color:#94a3b8;font-size:12px'>"
        f"UTC DATE · {NOW.strftime('%Y-%m-%d')}</div>",
        unsafe_allow_html=True,
    )

st.components.v1.html("""
<div style="text-align:center;font-family:Arial,sans-serif;padding:2px">
  <div id="utc-clock" style="font-size:30px;font-weight:700;color:#7dd3fc">
    --:--:--
  </div>
  <div style="font-size:11px;letter-spacing:2px;color:#94a3b8">
    COORDINATED UNIVERSAL TIME (UTC)
  </div>
</div>
<script>
function updateUTC() {
  const now = new Date();
  document.getElementById("utc-clock").textContent =
    now.toISOString().slice(11, 19);
}
updateUTC();
setInterval(updateUTC, 1000);
</script>
""", height=76)

st.divider()

# =========================================================
# FILTERS
# =========================================================

st.subheader("Hazard Monitor")

selected_hazard = st.radio(
    "Filter by hazard",
    HAZARDS,
    horizontal=True,
    format_func=lambda x: HA​ZARD_LABELS[x] if False else HAZARD_LABELS[x],
    label_visibility="collapsed",
)

filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 1])

default_start = TODAY_UTC - timedelta(days=6)

with filter_col1:
    start_date = st.date_input(
        "Start date (UTC)",
        value=default_start,
        max_value=TODAY_UTC,
        key="start_date",
    )

with filter_col2:
    end_date = st.date_input(
        "End date (UTC)",
        value=TODAY_UTC,
        min_value=start_date,
        max_value=TODAY_UTC,
        key="end_date",
    )

with filter_col3:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    if st.button("Last 7 days", use_container_width=True):
        st.session_state.start_date = TODAY_UTC - timedelta(days=6)
        st.session_state.end_date = TODAY_UTC
        st.rerun()

if start_date > end_date:
    st.error("Start date must be on or before end date.")
    st.stop()

action_col1, action_col2 = st.columns([1, 5])
with action_col1:
    if st.button("🔄 Refresh data", use_container_width=True):
        fetch_usgs.clear()
        fetch_gdacs.clear()
        st.rerun()

with action_col2:
    st.caption(
        "Sources: USGS earthquake observations and GDACS public disaster alerts. "
        "Times are shown in UTC."
    )

# =========================================================
# LOAD AND FILTER
# =========================================================

with st.spinner("Loading public disaster data..."):
    all_events, fetch_errors = load_events(start_date, end_date)

if selected_hazard != "All":
    events = [e for e in all_events if e["hazard"] == selected_hazard]
else:
    events = all_events

events.sort(
    key=lambda e: e["occurred"] or datetime.min.replace(tzinfo=UTC),
    reverse=True,
)

# =========================================================
# SUMMARY METRICS
# =========================================================

m1, m2, m3 = st.columns(3)

m1.metric("Events in selected period", len(events))
m2.metric(
    "Earthquake observations",
    sum(1 for e in events if e["hazard"] == "Earthquake"),
)
m3.metric(
    "GDACS alerts",
    sum(1 for e in events if e["source"] == "GDACS"),
)

if fetch_errors:
    with st.expander("Data source connection notices"):
        st.warning(
            "One or more sources could not be reached. The results may be incomplete."
        )
        for err in fetch_errors:
            st.code(err)

st.divider()

# =========================================================
# DETAILS DIALOG
# =========================================================

@st.dialog("Disaster details", width="large")
def show_details(event):
    st.markdown(f"### {event['title']}")
    st.caption(
        f"{event['hazard']} · {event['source']} · "
        f"{event['occurred'].strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )

    st.markdown("#### Available information")
    st.write(f"**Location:** {event['location']}")
    st.write(f"**Record type:** {event['status']}")

    if event["hazard"] == "Earthquake" and event.get("magnitude") is not None:
        st.write(f"**Magnitude:** {event['magnitude']}")

    st.markdown("#### Casualties and property damage")
    st.info(
        "This dashboard does not infer or calculate casualty figures or "
        "property damage from headlines. Consult the affected country's "
        "official disaster-management agency for confirmed figures."
    )

    st.write("**Deaths:** Unverified here")
    st.write("**Missing persons:** Unverified here")
    st.write("**Property damage:** Unverified here")

    st.caption(event["data_note"])

    if event.get("description"):
        st.markdown("#### Source description")
        st.write(event["description"])

    if event.get("latitude") is not None and event.get("longitude") is not None:
        st.markdown("#### Coordinates")
        st.code(
            f"Latitude: {event['latitude']}\n"
            f"Longitude: {event['longitude']}"
        )
        map_url = (
            "https://www.google.com/maps?q="
            f"{event['latitude']},{event['longitude']}"
        )
        st.link_button("Open location map", map_url, use_container_width=True)

    st.markdown("#### Official sources")
    st.link_button(
        f"Open original {event['source']} record",
        event["source_url"],
        use_container_width=True,
    )

    source_group = (
        "Earthquake" if event["hazard"] == "Earthquake"
        else event["hazard"]
    )
    source_links = official_sources_for(source_group)

    for name, url in list(source_links.items())[:8]:
        st.markdown(f"- [{name}]({url})")

    st.caption(
        "Official websites may publish revised figures after the initial alert. "
        "Always check the report's publication time and update time."
    )


# =========================================================
# EVENT CARDS
# =========================================================

st.subheader("Disaster Events")

if not events:
    st.info(
        "No matching events were returned for the selected dates and hazard. "
        "This does not prove that no disaster occurred."
    )
else:
    for start in range(0, len(events), 2):
        cols = st.columns(2)

        for offset, col in enumerate(cols):
            index = start + offset
            if index >= len(events):
                continue

            event = events[index]
            with col:
                occurred_text = event["occurred"].strftime(
                    "%Y-%m-%d %H:%M UTC"
                )

                st.markdown(
                    f"""
                    <div class="disaster-card">
                        <div class="tag">{html.escape(event['hazard'])}</div>
                        <div class="disaster-title">
                            {html.escape(event['title'])}
                        </div>
                        <div class="disaster-meta">
                            🕒 {html.escape(occurred_text)}
                        </div>
                        <div class="disaster-meta">
                            📡 Source: {html.escape(event['source'])}
                        </div>
                        <div class="disaster-meta">
                            📍 {html.escape(event['location'])}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                b1, b2 = st.columns(2)
                with b1:
                    if st.button(
                        "View Details",
                        key=f"details_{event['id']}",
                        use_container_width=True,
                    ):
                        show_details(event)

                with b2:
                    st.link_button(
                        "Official Record ↗",
                        event["source_url"],
                        use_container_width=True,
                    )

# =========================================================
# OFFICIAL SOURCES DIRECTORY
# =========================================================

st.divider()
st.subheader("Official Disaster Information")

st.write(
    "Use these official sources to verify casualty figures, missing persons, "
    "property damage, warnings, and situation reports. Availability varies "
    "by country and disaster."
)

source_tabs = st.tabs([
    "Global",
    "Earthquake",
    "Typhoon",
    "Wildfire",
    "Flood & Rain",
    "Other Hazards",
    "South Korea",
])

tab_groups = [
    ["Global"],
    ["Earthquake"],
    ["Typhoon"],
    ["Wildfire"],
    ["Flood", "Heavy Rain"],
    ["Drought", "Heavy Snow", "Heatwave", "Cold Wave", "Landslide"],
    ["South Korea"],
]

for tab, groups in zip(source_tabs, tab_groups):
    with tab:
        combined = {}
        for group in groups:
            combined.update(OFFICIAL_SOURCES.get(group, {}))

        cols = st.columns(2)
        for i, (name, url) in enumerate(combined.items()):
            with cols[i % 2]:
                st.markdown(
                    f"""
                    <div class="source-box">
                      <b>{html.escape(name)}</b><br>
                      <span class="small-muted">
                        Official disaster information
                      </span><br>
                      <a href="{html.escape(url, quote=True)}"
                         target="_blank" rel="noopener noreferrer">
                        Open official website ↗
                      </a>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

# =========================================================
# FOOTER
# =========================================================

st.divider()
st.caption(
    "WORLD DISASTER LIVE · Public data dashboard · "
    "Event coverage is not exhaustive. Always follow local emergency "
    "authorities and official warnings."
)
