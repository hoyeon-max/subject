
import html
import re
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import requests
import streamlit as st


# =====================================================
# 1. 기본 설정
# =====================================================

st.set_page_config(
    page_title="WORLD DISASTER LIVE",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

UTC = timezone.utc
NOW = datetime.now(UTC)
TODAY = NOW.date()

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
    "Disease",
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
    "Disease": "🦠 Disease",
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
        "GDACS": "https://www.gdacs.org/",
    },
    "Disease": {
        "WHO Disease Outbreak News": "https://www.who.int/emergencies/disease-outbreak-news",
        "WHO Health Emergency Dashboard": "https://extranet.who.int/publicemergency/",
        "WHO Ongoing Health Emergencies": "https://www.who.int/emergencies/situations",
        "CDC Current Outbreak List": "https://www.cdc.gov/outbreaks/",
        "CDC Health Alert Network": "https://www.cdc.gov/han/",
        "ECDC": "https://www.ecdc.europa.eu/en",
    },
    "South Korea": {
        "Korea Disease Control and Prevention Agency": "https://www.kdca.go.kr/",
        "KDCA Infectious Disease Portal": "https://dportal.kdca.go.kr/",
        "KDCA Disease Statistics Dashboard": "https://dportal.kdca.go.kr/pot/is/dashboardEDW.do",
        "Korea Meteorological Administration": "https://www.kma.go.kr/",
        "Ministry of the Interior and Safety": "https://www.mois.go.kr/",
        "Public Data Portal": "https://www.data.go.kr/",
    },
}


# =====================================================
# 2. 화면 디자인
# =====================================================

st.markdown("""
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
    min-height: 105px;
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

a {
    color: #7dd3fc !important;
}

hr {
    border-color: #2a3a55;
}
</style>
""", unsafe_allow_html=True)


# =====================================================
# 3. 공통 함수
# =====================================================

def safe_text(value, default="Not available"):
    if value is None:
        return default

    value = str(value).strip()

    return value if value else default


def safe_url(value, fallback):
    value = str(value or "").strip()

    if value.startswith("https://") or value.startswith("http://"):
        return value

    return fallback


def classify_hazard(text):
    text = (text or "").lower()

    patterns = [
        (
            "Disease",
            [
                "disease outbreak",
                "infectious disease",
                "epidemic",
                "pandemic",
                "outbreak",
                "ebola",
                "mpox",
                "monkeypox",
                "cholera",
                "measles",
                "dengue",
                "malaria",
                "marburg",
                "nipah",
                "avian influenza",
                "bird flu",
                "hantavirus",
                "mers",
                "covid",
            ],
        ),
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


def is_in_date_range(event_datetime, start_date, end_date):
    if event_datetime is None:
        return False

    return start_date <= event_datetime.date() <= end_date


def get_official_sources(hazard):
    mapping = {
        "Earthquake": ["Earthquake", "Global"],
        "Typhoon": ["Typhoon", "Global"],
        "Wildfire": ["Wildfire", "Global"],
        "Flood": ["Flood & Rain", "Global"],
        "Heavy Rain": ["Flood & Rain", "Global"],
        "Disease": ["Disease", "South Korea", "Global"],
        "Drought": ["Other Hazards", "Global"],
        "Heavy Snow": ["Other Hazards", "Global"],
        "Heatwave": ["Other Hazards", "Global"],
        "Cold Wave": ["Other Hazards", "Global"],
        "Landslide": ["Earthquake", "Global"],
        "Other": ["Global"],
    }

    result = {}

    for group in mapping.get(hazard, ["Global"]):
        result.update(OFFICIAL_SOURCES.get(group, {}))

    return result


# =====================================================
# 4. USGS 지진 API
# =====================================================

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
    events = []

    for item in payload.get("features", []):
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

        latitude = None
        longitude = None

        if len(coordinates) >= 2:
            try:
                longitude = float(coordinates[0])
                latitude = float(coordinates[1])
            except (ValueError, TypeError):
                pass

        magnitude = properties.get("mag")
        place = safe_text(properties.get("place"), "Unknown location")
        event_id = safe_text(item.get("id"), str(timestamp))

        events.append({
            "id": f"USGS:{event_id}",
            "title": f"Earthquake - {place}",
            "hazard": "Earthquake",
            "location": place,
            "occurred": occurred,
            "source": "USGS",
            "source_url": safe_url(
                properties.get("url"),
                "https://earthquake.usgs.gov/earthquakes/map/",
            ),
            "magnitude": magnitude,
            "latitude": latitude,
            "longitude": longitude,
            "description": safe_text(
                properties.get("title"),
                "USGS earthquake observation.",
            ),
            "data_note": (
                "USGS earthquake observations do not provide a complete "
                "global record of casualties or property damage."
            ),
        })

    return events


# =====================================================
# 5. GDACS 재난 RSS
# =====================================================

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

        if not is_in_date_range(occurred, start_date, end_date):
            continue

        hazard = classify_hazard(f"{title} {description}")

        if hazard == "Other":
            continue

        clean_description = re.sub(
            r"<[^>]*>",
            " ",
            description,
        )
        clean_description = html.unescape(clean_description)
        clean_description = re.sub(
            r"\s+",
            " ",
            clean_description,
        ).strip()

        events.append({
            "id": f"GDACS:{guid}",
            "title": html.unescape(safe_text(title, "Disaster alert")),
            "hazard": hazard,
            "location": "See original GDACS alert",
            "occurred": occurred,
            "source": "GDACS",
            "source_url": safe_url(link, "https://www.gdacs.org/"),
            "magnitude": None,
            "latitude": None,
            "longitude": None,
            "description": clean_description or "See original alert.",
            "data_note": (
                "This alert is not a complete standardized register "
                "of casualties or property damage."
            ),
        })

    return events


# =====================================================
# 6. 데이터 불러오기
# =====================================================

def load_events(start_date, end_date):
    start_iso = datetime.combine(
        start_date,
        time.min,
        tzinfo=UTC,
    ).isoformat()

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
            fetch_gdacs(
                start_date.isoformat(),
                end_date.isoformat(),
            )
        )
    except Exception as exc:
        errors.append(f"GDACS: {type(exc).__name__}: {exc}")

    unique = {}

    for event in events:
        unique[event["id"]] = event

    result = list(unique.values())

    result.sort(
        key=lambda event: event["occurred"] or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )

    return result, errors


# =====================================================
# 7. 상단 제목과 UTC 시계
# =====================================================

left, center, right = st.columns([2, 4, 2])

with left:
    st.caption("GLOBAL HAZARD MONITOR")

with center:
    st.markdown(
        """
        <div style="text-align:center;font-size:29px;font-weight:800;
                    letter-spacing:1.5px;">
            WORLD DISASTER LIVE
        </div>
        """,
        unsafe_allow_html=True,
    )

with right:
    st.markdown(
        f"""
        <div style="text-align:right;color:#94a3b8;font-size:12px">
            UTC DATE: {NOW.strftime('%Y-%m-%d')}
        </div>
        """,
        unsafe_allow_html=True,
    )

st.components.v1.html(
    """
    <div style="text-align:center;font-family:Arial;padding:4px">
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


# =====================================================
# 8. 날짜 및 재난 종류 선택
# =====================================================

st.subheader("Hazard Monitor")

if "start_date" not in st.session_state:
    st.session_state.start_date = TODAY - timedelta(days=6)

if "end_date" not in st.session_state:
    st.session_state.end_date = TODAY

preset1, preset2, preset3 = st.columns([1, 1, 5])

with preset1:
    if st.button("Last 7 days", use_container_width=True):
        st.session_state.start_date = TODAY - timedelta(days=6)
        st.session_state.end_date = TODAY
        st.rerun()

with preset2:
    if st.button("Today", use_container_width=True):
        st.session_state.start_date = TODAY
        st.session_state.end_date = TODAY
        st.rerun()

date_col1, date_col2 = st.columns(2)

with date_col1:
    start_date = st.date_input(
        "Start date (UTC)",
        key="start_date",
        max_value=TODAY,
    )

with date_col2:
    end_date = st.date_input(
        "End date (UTC)",
        key="end_date",
        max_value=TODAY,
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
        "Disease information is linked to official health authorities."
    )


# =====================================================
# 9. 데이터 표시
# =====================================================

with st.spinner("Loading public information..."):
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
            "Some sources could not be reached. "
            "Displayed information may be incomplete."
        )

        for error in errors:
            st.code(error)


# =====================================================
# 10. 질병 전용 공식 정보 영역
# =====================================================

def show_disease_portal():
    st.subheader("🦠 Global Disease Monitor")

    st.info(
        "질병 정보는 WHO와 각국 보건당국의 공식 발표를 기준으로 "
        "확인할 수 있어. 이 메뉴에서는 검증되지 않은 확진자나 "
        "사망자 수를 임의로 표시하지 않아."
    )

    st.markdown("### International Health Authorities")

    international_sources = [
        (
            "WHO Disease Outbreak News",
            "WHO가 공개하는 국제적으로 중요한 질병 발생 보고",
            "https://www.who.int/emergencies/disease-outbreak-news",
        ),
        (
            "WHO Health Emergency Dashboard",
            "진행 중인 국제 보건 비상사태와 공식 발표",
            "https://extranet.who.int/publicemergency/",
        ),
        (
            "WHO Ongoing Health Emergencies",
            "WHO가 대응하는 주요 보건 비상사태",
            "https://www.who.int/emergencies/situations",
        ),
        (
            "CDC Current Outbreak List",
            "미국 및 국제 감염병 발생 정보",
            "https://www.cdc.gov/outbreaks/",
        ),
        (
            "CDC Health Alert Network",
            "미국 보건당국의 공식 보건 경보",
            "https://www.cdc.gov/han/",
        ),
        (
            "European CDC",
            "유럽 질병예방통제센터의 감염병 감시 정보",
            "https://www.ecdc.europa.eu/en",
        ),
    ]

    for name, description, url in international_sources:
        st.markdown(
            f"""
            <div class="source-card">
                <b>{html.escape(name)}</b><br>
                <span class="source-muted">
                    {html.escape(description)}
                </span><br><br>
                <a href="{html.escape(url, quote=True)}"
                   target="_blank" rel="noopener noreferrer">
                    Open official website ↗
                </a>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### South Korea")

    korea_sources = [
        (
            "KDCA Infectious Disease Portal",
            "국내 감염병 발생 동향 및 감염병 정보",
            "https://dportal.kdca.go.kr/",
        ),
        (
            "KDCA Statistics Dashboard",
            "국내 감염병 통계와 지역별·기간별 발생 현황",
            "https://dportal.kdca.go.kr/pot/is/dashboardEDW.do",
        ),
        (
            "KDCA Disease Information",
            "질병관리청 공식 발표 및 예방 정보",
            "https://www.kdca.go.kr/",
        ),
    ]

    for name, description, url in korea_sources:
        st.markdown(
            f"""
            <div class="source-card">
                <b>{html.escape(name)}</b><br>
                <span class="source-muted">
                    {html.escape(description)}
                </span><br><br>
                <a href="{html.escape(url, quote=True)}"
                   target="_blank" rel="noopener noreferrer">
                    Open official website ↗
                </a>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.caption(
        "각 기관의 발표 시점, 통계 기준, 잠정치 여부를 확인해야 해. "
        "기관마다 집계 기준이 다를 수 있어."
    )


if selected_hazard == "Disease":
    show_disease_portal()
    st.divider()


# =====================================================
# 11. 상세 정보 팝업
# =====================================================

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
        "이 대시보드는 확인되지 않은 피해 수치를 추정하지 않아. "
        "피해 통계는 해당 국가의 공식 재난관리기관 발표를 확인해 줘."
    )

    st.write("**Deaths:** Not verified")
    st.write("**Missing persons:** Not verified")
    st.write("**Property damage:** Not verified")

    st.caption(event["data_note"])

    if event.get("description"):
        st.markdown("#### Description")
        st.write(event["description"])

    st.markdown("#### Official sources")

    st.link_button(
        f"Open {event['source']} original record",
        event["source_url"],
        use_container_width=True,
    )

    for name, url in get_official_sources(event["hazard"]).items():
        st.markdown(f"- [{name}]({url})")


# =====================================================
# 12. 재난 카드
# =====================================================

if selected_hazard != "Disease":
    st.divider()
    st.subheader("Disaster Events")

    if not events:
        st.info(
            "No matching events were returned for this period. "
            "This does not necessarily mean that no disaster occurred."
        )

    else:
        for row_start in range(0, len(events), 2):
            columns = st.columns(2)

            for offset, column in enumerate(columns):
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

                    st.markdown(
                        f"""
                        <div class="disaster-card">
                            <span class="hazard-tag">
                                {html.escape(event['hazard'])}
                            </span>
                            <div class="disaster-title">
                                {html.escape(event['title'])}
                            </div>
                            <div class="disaster-meta">
                                Time: {html.escape(occurred_text)}
                            </div>
                            <div class="disaster-meta">
                                Source: {html.escape(event['source'])}
                            </div>
                            <div class="disaster-meta">
                                Location: {html.escape(event['location'])}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    button1, button2 = st.columns(2)

                    with button1:
                        if st.button(
                            "View Details",
                            key=f"details_{event['id']}",
                            use_container_width=True,
                        ):
                            show_details(event)

                    with button2:
                        st.link_button(
                            "Official Record",
                            event["source_url"],
                            use_container_width=True,
                        )


# =====================================================
# 13. 공식 기관 사이트 디렉터리
# =====================================================

st.divider()
st.subheader("Official Information Directory")

tab_names = [
    "Global",
    "Earthquake",
    "Typhoon",
    "Wildfire",
    "Flood & Rain",
    "Other Hazards",
    "Disease",
    "South Korea",
]

tabs = st.tabs(tab_names)

for tab, group_name in zip(tabs, tab_names):
    with tab:
        sources = OFFICIAL_SOURCES.get(group_name, {})

        if not sources:
            st.info("No sources configured.")
            continue

        columns = st.columns(2)

        for index, (name, url) in enumerate(sources.items()):
            with columns[index % 2]:
                st.markdown(
                    f"""
                    <div class="source-card">
                        <b>{html.escape(name)}</b><br>
                        <span class="source-muted">
                            Official information and reports
                        </span><br><br>
                        <a href="{html.escape(url, quote=True)}"
                           target="_blank" rel="noopener noreferrer">
                            Open official website ↗
                        </a>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# =====================================================
# 14. 하단 안내
# =====================================================

st.divider()

st.caption(
    "WORLD DISASTER LIVE | Global Disaster & Disease Monitor | "
    "Public information dashboard | "
    "Always follow official health and emergency authority guidance."
)
