
import html
import re
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import pandas as pd
import requests
import streamlit as st


# =========================================================
# 1. APP CONFIG
# =========================================================

st.set_page_config(
    page_title="WORLD DISASTER LIVE",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

UTC = timezone.utc
CURRENT_UTC = datetime.now(UTC)
TODAY_UTC = CURRENT_UTC.date()

USGS_API = "https://earthquake.usgs.gov/fdsnws/event/1/query"
GDACS_RSS = "https://www.gdacs.org/xml/rss.xml"

HAZARDS = [
    "All",
    "Typhoon",
    "Earthquake",
    "Wildfire",
    "Flood",
    "Heavy Rain",
    "Drought",
    "Heavy Snow",
    "Heatwave",
    "Cold Wave",
    "Landslide",
]

HAZARD_LABELS = {
    "All": "🌐 All",
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

OFFICIAL_SOURCES = {
    "Global": {
        "GDACS": "https://www.gdacs.org/",
        "UNDRR": "https://www.undrr.org/",
        "ReliefWeb": "https://reliefweb.int/",
        "WMO": "https://wmo.int/",
    },
    "Earthquake": {
        "USGS Earthquake Map": "https://earthquake.usgs.gov/earthquakes/map/",
        "USGS Earthquake API": "https://earthquake.usgs.gov/fdsnws/event/1/",
        "USGS Landslide Hazards": "https://www.usgs.gov/programs/landslide-hazards",
    },
    "Typhoon": {
        "NOAA National Hurricane Center": "https://www.nhc.noaa.gov/",
        "JTWC": "https://www.metoc.navy.mil/jtwc/jtwc.html",
        "GDACS": "https://www.gdacs.org/",
    },
    "Wildfire": {
        "NASA FIRMS": "https://firms.modaps.eosdis.nasa.gov/",
        "Copernicus Emergency Management": "https://emergency.copernicus.eu/",
    },
    "Flood & Rain": {
        "Copernicus Emergency Management": "https://emergency.copernicus.eu/",
        "GDACS": "https://www.gdacs.org/",
        "WMO": "https://wmo.int/",
    },
    "Other Hazards": {
        "UNDRR": "https://www.undrr.org/",
        "WMO": "https://wmo.int/",
        "WHO": "https://www.who.int/",
        "GDACS": "https://www.gdacs.org/",
    },
    "South Korea": {
        "Ministry of the Interior and Safety": "https://www.mois.go.kr/",
        "Korea Meteorological Administration": "https://www.kma.go.kr/",
        "Korea Public Data Portal": "https://www.data.go.kr/",
    },
}


# =========================================================
# 2. STYLE
# =========================================================

st.markdown(
    """
    <style>
    .stApp {
        background-color: #0f172a;
        color: #e5e7eb;
    }

    header[data-testid="stHeader"] {
        background-color: #0f172a;
    }

    .block-container {
        max-width: 1500px;
        padding-top: 1.4rem;
        padding-bottom: 3rem;
    }

    h1, h2, h3, h4, p, label {
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
        min-height: 190px;
        margin-bottom: 8px;
        overflow-wrap: anywhere;
    }

    .disaster-title {
        font-size: 18px;
        font-weight: 700;
        line-height: 1.5;
        margin: 8px 0 12px 0;
        color: #f1f5f9;
    }

    .disaster-meta {
        font-size: 13px;
        color: #b4c2d5;
        margin: 6px 0;
    }

    .hazard-tag {
        display: inline-block;
        background: #263750;
        color: #bae6fd;
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 12px;
    }

    .source-card {
        background: #172238;
        border: 1px solid #2a3a55;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        overflow-wrap: anywhere;
    }

    .source-muted {
        color: #94a3b8;
        font-size: 12px;
    }

    div.stButton > button {
        border-radius: 8px;
        min-height: 40px;
        border: 1px solid #334766;
    }

    div[data-testid="stDialog"] {
        background-color: #0f172a;
    }

    a {
        color: #7dd3fc !important;
    }

    hr {
        border-color: #2a3a55;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 3. COMMON HELPERS
# =========================================================

def safe_text(value, default="Not available"):
    """Convert a value into safe display text."""
    if value is None:
        return default

    text = str(value).strip()

    if not text:
        return default

    return text


def safe_url(value, fallback):
    """Only allow HTTP and HTTPS links."""
    value = str(value or "").strip()

    if value.startswith("https://") or value.startswith("http://"):
        return value

    return fallback


def classify_hazard(text):
    text = (text or "").lower()

    # More specific patterns are checked first.
    patterns = [
        ("Earthquake", ["earthquake", "seismic"]),
        (
            "Typhoon",
            [
                "tropical cyclone",
                "typhoon",
                "hurricane",
                "cyclone",
                "tropical storm",
            ],
        ),
        ("Wildfire", ["wildfire", "wild fire", "forest fire"]),
        ("Landslide", ["landslide", "mudslide"]),
        ("Drought", ["drought"]),
        ("Heatwave", ["heatwave", "heat wave", "extreme heat"]),
        ("Cold Wave", ["cold wave", "cold spell", "extreme cold"]),
        ("Heavy Snow", ["heavy snow", "snowstorm", "blizzard"]),
        ("Flood", ["flood", "flash flood"]),
        ("Heavy Rain", ["heavy rain", "extreme rainfall", "rainfall"]),
    ]

    for hazard, keywords in patterns:
        if any(keyword in text for keyword in keywords):
            return hazard

    return "Other"


def make_event_id(source, external_id):
    return f"{source}:{external_id}"


def parse_rss_date(value):
    if not value:
        return None

    try:
        parsed = parsedate_to_datetime(value.strip())

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)

        return parsed.astimezone(UTC)

    except (ValueError, TypeError, OverflowError):
        return None


def parse_iso_datetime(value):
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)

        return parsed.astimezone(UTC)

    except (ValueError, TypeError, OverflowError):
        return None


def is_in_date_range(event_datetime, start_date, end_date):
    if event_datetime is None:
        return False

    return start_date <= event_datetime.date() <= end_date


def get_official_sources(hazard):
    """Select relevant official source links."""
    source_groups = {
        "Earthquake": ["Earthquake", "Global"],
        "Typhoon": ["Typhoon", "Global"],
        "Wildfire": ["Wildfire", "Global"],
        "Flood": ["Flood & Rain", "Global"],
        "Heavy Rain": ["Flood & Rain", "Global"],
        "Drought": ["Other Hazards", "Global"],
        "Heavy Snow": ["Other Hazards", "Global"],
        "Heatwave": ["Other Hazards", "Global"],
        "Cold Wave": ["Other Hazards", "Global"],
        "Landslide": ["Earthquake", "Global"],
        "Other": ["Global"],
    }

    groups = source_groups.get(hazard, ["Global"])
    results = {}

    for group in groups:
        results.update(OFFICIAL_SOURCES.get(group, {}))

    return results


# =========================================================
# 4. USGS EARTHQUAKE API
# =========================================================

@st.cache_data(ttl=300, show_spinner=False)
def fetch_usgs(start_iso, end_iso):
    params = {
        "format": "geojson",
        "starttime": start_iso,
        "endtime": end_iso,
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
    features = payload.get("features", [])

    events = []

    for item in features:
        properties = item.get("properties") or {}
        geometry = item.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []

        timestamp = properties.get("time")

        if timestamp is None:
            continue

        try:
            occurred = datetime.fromtimestamp(
                float(timestamp) / 1000,
                tz=UTC,
            )
        except (ValueError, TypeError, OverflowError, OSError):
            continue

        magnitude = properties.get("mag")
        place = safe_text(properties.get("place"), "Location not specified")
        external_id = safe_text(item.get("id"), str(timestamp))

        latitude = None
        longitude = None

        if len(coordinates) >= 2:
            try:
                longitude = float(coordinates[0])
                latitude = float(coordinates[1])
            except (ValueError, TypeError):
                latitude = None
                longitude = None

        event_url = safe_url(
            properties.get("url"),
            "https://earthquake.usgs.gov/earthquakes/map/",
        )

        events.append({
            "id": make_event_id("USGS", external_id),
            "title": f"Earthquake - {place}",
            "hazard": "Earthquake",
            "location": place,
            "occurred": occurred,
            "source": "USGS",
            "source_url": event_url,
            "magnitude": magnitude,
            "latitude": latitude,
            "longitude": longitude,
            "description": safe_text(
                properties.get("title"),
                "USGS earthquake observation.",
            ),
            "status": "Official observation",
            "data_note": (
                "USGS provides earthquake observations. This record alone "
                "does not establish deaths, missing persons, or total "
                "property damage."
            ),
        })

    return events


# =========================================================
# 5. GDACS PUBLIC RSS
# =========================================================

@st.cache_data(ttl=300, show_spinner=False)
def fetch_gdacs(start_iso, end_iso):
    start_date = date.fromisoformat(start_iso)
    end_date = date.fromisoformat(end_iso)

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
        link = item.findtext("link", default="")
        description = item.findtext("description", default="")
        pub_date = item.findtext("pubDate", default="")
        guid = item.findtext("guid", default=link or title)

        occurred = parse_rss_date(pub_date)

        # Do not invent a date if the feed has no usable timestamp.
        if not is_in_date_range(occurred, start_date, end_date):
            continue

        combined = f"{title} {description}"
        hazard = classify_hazard(combined)

        if hazard == "Other":
            continue

        clean_description = re.sub(r"<[^>]*>", " ", description)
        clean_description = html.unescape(clean_description)
        clean_description = re.sub(r"\s+", " ", clean_description).strip()

        events.append({
            "id": make_event_id("GDACS", safe_text(guid, title)),
            "title": html.unescape(safe_text(title, "Disaster alert")),
            "hazard": hazard,
            "location": "See original GDACS alert",
            "occurred": occurred,
            "source": "GDACS",
            "source_url": safe_url(link, "https://www.gdacs.org/"),
            "magnitude": None,
            "latitude": None,
            "longitude": None,
            "description": clean_description or "See the original alert.",
            "status": "Official alert feed",
            "data_note": (
                "GDACS alert records are not a complete standardized "
                "register of casualties or property damage. Consult the "
                "affected country's official disaster authority."
            ),
        })

    return events


# =========================================================
# 6. LOAD DATA WITH ERROR HANDLING
# =========================================================

def load_events(start_date, end_date):
    start_iso = datetime.combine(
        start_date,
        time.min,
        tzinfo=UTC,
    ).isoformat()

    # Use the start of the day after end_date as the exclusive endpoint.
    end_exclusive = datetime.combine(
        end_date + timedelta(days=1),
        time.min,
        tzinfo=UTC,
    ).isoformat()

    events = []
    errors = []

    try:
        events.extend(fetch_usgs(start_iso, end_exclusive))
    except Exception as exc:
        errors.append(f"USGS: {type(exc).__name__}: {exc}")

    try:
        events.extend(
            fetch_gdacs(start_date.isoformat(), end_date.isoformat())
        )
    except Exception as exc:
        errors.append(f"GDACS: {type(exc).__name__}: {exc}")

    # Remove duplicate IDs.
    unique_events = {}

    for event in events:
        unique_events[event["id"]] = event

    result = list(unique_events.values())

    result.sort(
        key=lambda event: event["occurred"] or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )

    return result, errors


# =========================================================
# 7. UTC CLOCK AND HEADER
# =========================================================

header_left, header_center, header_right = st.columns([2, 4, 2])

with header_left:
    st.caption("GLOBAL HAZARD MONITOR")

with header_center:
    st.markdown(
        """
        <div style="text-align:center;font-size:29px;font-weight:800;
                    letter-spacing:1.5px;">
            WORLD DISASTER LIVE
        </div>
        """,
        unsafe_allow_html=True,
    )

with header_right:
    st.markdown(
        f"<div style='text-align:right;color:#94a3b8;font-size:12px'>"
        f"UTC DATE: {CURRENT_UTC.strftime('%Y-%m-%d')}</div>",
        unsafe_allow_html=True,
    )

st.components.v1.html(
    """
    <div style="text-align:center;font-family:Arial,sans-serif;padding:4px">
        <div id="utc-clock"
             style="font-size:30px;font-weight:700;color:#7dd3fc">
            --:--:--
        </div>
        <div style="font-size:11px;letter-spacing:2px;color:#94a3b8">
            COORDINATED UNIVERSAL TIME (UTC)
        </div>
    </div>
    <script>
    function updateUTC() {
        const clock = document.getElementById("utc-clock");
        if (!clock) return;
        clock.textContent = new Date().toISOString().slice(11, 19);
    }
    updateUTC();
    setInterval(updateUTC, 1000);
    </script>
    """,
    height=78,
)

st.divider()


# =========================================================
# 8. DATE FILTERS
# =========================================================

st.subheader("Hazard Monitor")

# Initialize widget state before creating date_input widgets.
if "start_date" not in st.session_state:
    st.session_state.start_date = TODAY_UTC - timedelta(days=6)

if "end_date" not in st.session_state:
    st.session_state.end_date = TODAY_UTC

# Keep dates within allowed bounds after the app stays open across days.
if st.session_state.start_date > TODAY_UTC:
    st.session_state.start_date = TODAY_UTC

if st.session_state.end_date > TODAY_UTC:
    st.session_state.end_date = TODAY_UTC

preset1, preset2, preset3 = st.columns([1, 1, 5])

with preset1:
    if st.button("Last 7 days", use_container_width=True):
        st.session_state.start_date = TODAY_UTC - timedelta(days=6)
        st.session_state.end_date = TODAY_UTC
        st.rerun()

with preset2:
    if st.button("Today", use_container_width=True):
        st.session_state.start_date = TODAY_UTC
        st.session_state.end_date = TODAY_UTC
        st.rerun()

date_col1, date_col2 = st.columns(2)

with date_col1:
    start_date = st.date_input(
        "Start date (UTC)",
        key="start_date",
        max_value=TODAY_UTC,
    )

with date_col2:
    end_date = st.date_input(
        "End date (UTC)",
        key="end_date",
        max_value=TODAY_UTC,
    )

if start_date > end_date:
    st.error("Start date must be on or before end date.")
    st.stop()

selected_hazard = st.radio(
    "Filter by hazard",
    HAZARDS,
    horizontal=True,
    format_func=lambda value: HAZARD_LABELS[value],
    label_visibility="collapsed",
)

refresh_col, note_col = st.columns([1, 5])

with refresh_col:
    if st.button("Refresh data", use_container_width=True):
        fetch_usgs.clear()
        fetch_gdacs.clear()
        st.rerun()

with note_col:
    st.caption(
        "Sources: USGS earthquake observations and GDACS public alerts. "
        "Data may be incomplete or delayed."
    )


# =========================================================
# 9. FETCH AND FILTER
# =========================================================

with st.spinner("Loading official public data..."):
    all_events, errors = load_events(start_date, end_date)

if selected_hazard == "All":
    events = all_events
else:
    events = [
        event for event in all_events
        if event["hazard"] == selected_hazard
    ]

earthquake_count = sum(
    1 for event in events if event["hazard"] == "Earthquake"
)

gdacs_count = sum(
    1 for event in events if event["source"] == "GDACS"
)

metric1, metric2, metric3 = st.columns(3)

metric1.metric("Events returned", len(events))
metric2.metric("Earthquake observations", earthquake_count)
metric3.metric("GDACS alerts", gdacs_count)

if errors:
    with st.expander("Data source connection issues"):
        st.warning(
            "Some data sources could not be reached. "
            "The displayed event list may be incomplete."
        )

        for error in errors:
            st.code(error)


# =========================================================
# 10. DETAILS DIALOG
# =========================================================

@st.dialog("Disaster details", width="large")
def show_details(event):
    st.markdown(f"### {event['title']}")

    occurred = event.get("occurred")
    occurred_text = (
        occurred.strftime("%Y-%m-%d %H:%M:%S UTC")
        if occurred
        else "Time unavailable"
    )

    st.caption(
        f"{event['hazard']} | {event['source']} | {occurred_text}"
    )

    st.markdown("#### Event information")
    st.write(f"**Location:** {event['location']}")
    st.write(f"**Record type:** {event['status']}")

    magnitude = event.get("magnitude")

    if event["hazard"] == "Earthquake" and magnitude is not None:
        st.write(f"**Magnitude:** {magnitude}")

    latitude = event.get("latitude")
    longitude = event.get("longitude")

    if latitude is not None and longitude is not None:
        st.markdown("#### Coordinates")
        st.code(f"Latitude: {latitude}\nLongitude: {longitude}")

        map_url = (
            "https://www.google.com/maps?"
            + urlencode({"q": f"{latitude},{longitude}"})
        )

        st.link_button(
            "Open map",
            map_url,
            use_container_width=True,
        )

    st.markdown("#### Casualties and property damage")

    st.info(
        "This dashboard does not estimate casualty figures or property "
        "damage from headlines. Check the official reports from the "
        "affected country's government or disaster-management agency."
    )

    st.write("**Deaths:** Not verified by this dashboard")
    st.write("**Missing persons:** Not verified by this dashboard")
    st.write("**Property damage:** Not verified by this dashboard")

    st.caption(event["data_note"])

    st.markdown("#### Original record")

    st.link_button(
        f"Open {event['source']} record",
        event["source_url"],
        use_container_width=True,
    )

    st.markdown("#### Related official sources")

    source_links = get_official_sources(event["hazard"])

    for name, url in source_links.items():
        st.markdown(f"- [{name}]({url})")

    st.caption(
        "Official reports may be updated after the initial alert. "
        "Check the report date and the latest revision."
    )


# =========================================================
# 11. EVENT CARDS
# =========================================================

st.divider()
st.subheader("Disaster Events")

if not events:
    st.info(
        "No matching events were returned for the selected period. "
        "This does not necessarily mean that no disaster occurred."
    )

else:
    for row_start in range(0, len(events), 2):
        card_columns = st.columns(2)

        for offset, column in enumerate(card_columns):
            index = row_start + offset

            if index >= len(events):
                continue

            event = events[index]

            with column:
                occurred = event.get("occurred")
                occurred_text = (
                    occurred.strftime("%Y-%m-%d %H:%M UTC")
                    if occurred
                    else "Time unavailable"
                )

                hazard_text = html.escape(event["hazard"])
                title_text = html.escape(event["title"])
                source_text = html.escape(event["source"])
                location_text = html.escape(event["location"])
                time_text = html.escape(occurred_text)

                st.markdown(
                    f"""
                    <div class="disaster-card">
                        <span class="hazard-tag">{hazard_text}</span>
                        <div class="disaster-title">{title_text}</div>
                        <div class="disaster-meta">Time: {time_text}</div>
                        <div class="disaster-meta">Source: {source_text}</div>
                        <div class="disaster-meta">Location: {location_text}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                button_col1, button_col2 = st.columns(2)

                with button_col1:
                    if st.button(
                        "View Details",
                        key=f"details_{event['id']}",
                        use_container_width=True,
                    ):
                        show_details(event)

                with button_col2:
                    st.link_button(
                        "Official Record",
                        event["source_url"],
                        use_container_width=True,
                    )


# =========================================================
# 12. OFFICIAL SOURCES DIRECTORY
# =========================================================

st.divider()
st.subheader("Official Disaster Information")

st.write(
    "Open the official websites below to check government reports, "
    "casualty figures, missing persons, damage assessments, and warnings."
)

source_tab_names = [
    "Global",
    "Earthquake",
    "Typhoon",
    "Wildfire",
    "Flood & Rain",
    "Other Hazards",
    "South Korea",
]

source_tabs = st.tabs(source_tab_names)

for tab, group_name in zip(source_tabs, source_tab_names):
    with tab:
        sources = OFFICIAL_SOURCES.get(group_name, {})

        if not sources:
            st.info("No sources configured for this category.")
            continue

        source_columns = st.columns(2)

        for index, (name, url) in enumerate(sources.items()):
            with source_columns[index % 2]:
                escaped_name = html.escape(name)
                escaped_url = html.escape(url, quote=True)

                st.markdown(
                    f"""
                    <div class="source-card">
                        <strong>{escaped_name}</strong><br>
                        <span class="source-muted">
                            Official information and reports
                        </span><br><br>
                        <a href="{escaped_url}" target="_blank"
                           rel="noopener noreferrer">
                           Open official website
                        </a>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# =========================================================
# 13. FOOTER
# =========================================================

st.divider()

st.caption(
    "WORLD DISASTER LIVE | Public information dashboard | "
    "Coverage is not exhaustive. Follow official local emergency guidance."
)
