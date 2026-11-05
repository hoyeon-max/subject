
import streamlit as st
import requests
import pandas as pd
import xml.etree.ElementTree as ET

from datetime import datetime, date, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import escape
from urllib.parse import quote


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="WORLD DISASTER LIVE",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

UTC = timezone.utc

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
    "Disease"
]

HAZARD_LABELS = {
    "All": "ALL",
    "Typhoon": "TYPHOON",
    "Earthquake": "EARTHQUAKE",
    "Wildfire": "WILDFIRE",
    "Flood": "FLOOD",
    "Heavy Rain": "HEAVY RAIN",
    "Drought": "DROUGHT",
    "Heavy Snow": "HEAVY SNOW",
    "Heatwave": "HEATWAVE",
    "Cold Wave": "COLD WAVE",
    "Landslide": "LANDSLIDE",
    "Disease": "DISEASE"
}

HAZARD_EMOJI = {
    "Typhoon": "🌀",
    "Earthquake": "🌎",
    "Wildfire": "🔥",
    "Flood": "🌊",
    "Heavy Rain": "🌧️",
    "Drought": "☀️",
    "Heavy Snow": "❄️",
    "Heatwave": "🌡️",
    "Cold Wave": "🥶",
    "Landslide": "⛰️",
    "Disease": "🦠",
    "Unknown": "⚠️"
}

OFFICIAL_SOURCES = {
    "Earthquake": [
        ("USGS Earthquake Map", "https://earthquake.usgs.gov/earthquakes/map/"),
        ("USGS Earthquake Search", "https://earthquake.usgs.gov/earthquakes/search/")
    ],
    "Typhoon": [
        ("NOAA National Hurricane Center", "https://www.nhc.noaa.gov/"),
        ("JTWC", "https://www.metoc.navy.mil/jtwc/jtwc.html"),
        ("GDACS", "https://www.gdacs.org/")
    ],
    "Wildfire": [
        ("NASA FIRMS", "https://firms.modaps.eosdis.nasa.gov/"),
        ("Copernicus Emergency Management", "https://emergency.copernicus.eu/")
    ],
    "Flood": [
        ("GDACS", "https://www.gdacs.org/"),
        ("Copernicus Emergency Management", "https://emergency.copernicus.eu/")
    ],
    "Heavy Rain": [
        ("GDACS", "https://www.gdacs.org/"),
        ("NOAA", "https://www.noaa.gov/")
    ],
    "Drought": [
        ("UNDRR", "https://www.undrr.org/"),
        ("Copernicus", "https://climate.copernicus.eu/")
    ],
    "Heavy Snow": [
        ("NOAA", "https://www.noaa.gov/"),
        ("GDACS", "https://www.gdacs.org/")
    ],
    "Heatwave": [
        ("WHO", "https://www.who.int/"),
        ("WMO", "https://wmo.int/")
    ],
    "Cold Wave": [
        ("NOAA", "https://www.noaa.gov/"),
        ("WMO", "https://wmo.int/")
    ],
    "Landslide": [
        ("NASA Landslide", "https://landslides.nasa.gov/"),
        ("GDACS", "https://www.gdacs.org/")
    ],
    "Disease": [
        ("WHO Disease Outbreak News", "https://www.who.int/emergencies/disease-outbreak-news"),
        ("WHO Health Emergencies", "https://www.who.int/emergencies/situations"),
        ("WHO Health Emergency Dashboard", "https://extranet.who.int/publicemergency/"),
        ("CDC Current Outbreak List", "https://www.cdc.gov/outbreaks/"),
        ("ECDC", "https://www.ecdc.europa.eu/en"),
        ("KDCA 감염병 포털", "https://dportal.kdca.go.kr/")
    ]
}

SOUTH_KOREA_SOURCES = [
    ("질병관리청", "https://www.kdca.go.kr/"),
    ("질병관리청 감염병 포털", "https://dportal.kdca.go.kr/"),
    ("질병관리청 통계", "https://dportal.kdca.go.kr/pot/is/dashboardEDW.do"),
    ("행정안전부", "https://www.mois.go.kr/"),
    ("기상청", "https://www.weather.go.kr/"),
    ("공공데이터포털", "https://www.data.go.kr/")
]


# =========================================================
# 디자인
# =========================================================

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700;800&display=swap');

    .stApp {
        background: #0f172a;
        color: #e2e8f0;
        font-family: 'Inter', sans-serif;
    }

    header[data-testid="stHeader"] {
        background: rgba(15, 23, 42, 0.95);
    }

    section[data-testid="stSidebar"] {
        background: #111c32;
        border-right: 1px solid #26354e;
    }

    .main-title {
        font-size: 34px;
        font-weight: 800;
        letter-spacing: 2px;
        color: #f8fafc;
        margin-bottom: 0;
    }

    .sub-title {
        color: #94a3b8;
        font-size: 13px;
        letter-spacing: 2px;
        margin-top: 4px;
    }

    .section-title {
        color: #cbd5e1;
        font-size: 17px;
        font-weight: 700;
        margin-top: 22px;
        margin-bottom: 12px;
    }

    .event-card {
        background: #17243a;
        border: 1px solid #293b56;
        border-radius: 12px;
        padding: 17px;
        margin-bottom: 12px;
        min-height: 175px;
    }

    .event-type {
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 1.5px;
        color: #60a5fa;
    }

    .event-title {
        font-size: 17px;
        font-weight: 700;
        color: #f1f5f9;
        margin-top: 9px;
        margin-bottom: 9px;
        line-height: 1.4;
    }

    .event-info {
        font-size: 12px;
        color: #94a3b8;
        line-height: 1.8;
    }

    .metric-card {
        background: #17243a;
        border: 1px solid #293b56;
        border-radius: 10px;
        padding: 16px;
    }

    .metric-label {
        color: #94a3b8;
        font-size: 12px;
    }

    .metric-value {
        color: #f8fafc;
        font-size: 25px;
        font-weight: 800;
        margin-top: 6px;
    }

    .source-box {
        background: #17243a;
        border: 1px solid #293b56;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
    }

    .source-box a {
        color: #60a5fa !important;
        text-decoration: none;
        font-size: 13px;
    }

    .notice {
        background: #17243a;
        border: 1px solid #334155;
        border-radius: 9px;
        padding: 13px;
        color: #cbd5e1;
        font-size: 13px;
        line-height: 1.7;
    }

    div[data-testid="stButton"] button {
        background: #1e293b;
        color: #cbd5e1;
        border: 1px solid #334155;
        border-radius: 8px;
        font-weight: 700;
    }

    div[data-testid="stButton"] button:hover {
        background: #2563eb;
        color: white;
        border-color: #3b82f6;
    }

    a {
        color: #60a5fa;
    }

    footer {
        visibility: hidden;
    }
</style>
""", unsafe_allow_html=True)


# =========================================================
# UTC 시계
# =========================================================

@st.fragment(run_every="1s")
def show_utc_clock():
    now = datetime.now(UTC)

    left, center, right = st.columns([1, 2, 1])

    with left:
        st.markdown(
            f"<div style='color:#94a3b8;font-size:13px;padding-top:14px;'>"
            f"{now.strftime('%Y-%m-%d')}</div>",
            unsafe_allow_html=True
        )

    with center:
        st.markdown(
            f"""
            <div style="text-align:center;">
                <div style="font-family:'Roboto Mono';font-size:31px;
                            font-weight:700;color:#60a5fa;">
                    {now.strftime('%H:%M:%S')}
                </div>
                <div style="font-size:10px;letter-spacing:4px;color:#94a3b8;">
                    UNIVERSAL TIME COORDINATED
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with right:
        st.markdown(
            "<div style='text-align:right;color:#94a3b8;"
            "font-size:12px;padding-top:14px;'>UTC</div>",
            unsafe_allow_html=True
        )


# =========================================================
# 데이터 분류
# =========================================================

def classify_hazard(text):
    text = str(text).lower()

    patterns = {
        "Typhoon": [
            "typhoon", "hurricane", "cyclone", "tropical storm",
            "tropical cyclone"
        ],
        "Earthquake": [
            "earthquake", "seismic", "magnitude"
        ],
        "Wildfire": [
            "wildfire", "forest fire", "bushfire"
        ],
        "Flood": [
            "flood", "flash flood", "inundation"
        ],
        "Heavy Rain": [
            "heavy rain", "rainfall", "monsoon", "precipitation"
        ],
        "Drought": [
            "drought", "water scarcity"
        ],
        "Heavy Snow": [
            "heavy snow", "snowstorm", "blizzard"
        ],
        "Heatwave": [
            "heatwave", "extreme heat", "high temperature"
        ],
        "Cold Wave": [
            "cold wave", "extreme cold", "cold spell"
        ],
        "Landslide": [
            "landslide", "mudslide", "rockslide"
        ]
    }

    for hazard, keywords in patterns.items():
        if any(keyword in text for keyword in keywords):
            return hazard

    return "Unknown"


# =========================================================
# 날짜 처리
# =========================================================

def to_utc_datetime(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    try:
        parsed = parsedate_to_datetime(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except Exception:
        pass

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except Exception:
        return None


# =========================================================
# USGS 지진 데이터
# =========================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_usgs(start_date, end_date):
    start_dt = datetime.combine(
        start_date, time.min, tzinfo=UTC
    )
    end_dt = datetime.combine(
        end_date + timedelta(days=1), time.min, tzinfo=UTC
    )

    params = {
        "format": "geojson",
        "starttime": start_dt.strftime("%Y-%m-%d"),
        "endtime": end_dt.strftime("%Y-%m-%d"),
        "orderby": "time",
        "limit": 20000
    }

    response = requests.get(
        USGS_API,
        params=params,
        timeout=25,
        headers={"User-Agent": "WorldDisasterLive/1.0"}
    )
    response.raise_for_status()

    payload = response.json()
    events = []

    for item in payload.get("features", []):
        properties = item.get("properties", {})
        geometry = item.get("geometry", {})

        coordinates = geometry.get("coordinates") or []

        if len(coordinates) < 2:
            latitude = None
            longitude = None
        else:
            longitude = coordinates[0]
            latitude = coordinates[1]

        timestamp = properties.get("time")

        if timestamp is not None:
            event_time = datetime.fromtimestamp(
                timestamp / 1000,
                tz=UTC
            )
        else:
            event_time = None

        magnitude = properties.get("mag")
        place = properties.get("place") or "위치 정보 없음"

        if magnitude is None:
            magnitude_text = "규모 미확인"
        else:
            magnitude_text = f"M {magnitude:.1f}"

        events.append({
            "id": item.get("id"),
            "hazard": "Earthquake",
            "title": f"Earthquake - {magnitude_text}",
            "description": place,
            "location": place,
            "time": event_time,
            "latitude": latitude,
            "longitude": longitude,
            "magnitude": magnitude,
            "source": "USGS",
            "url": properties.get("url") or "https://earthquake.usgs.gov/",
            "damage": "미확인"
        })

    return events


# =========================================================
# GDACS RSS 데이터
# =========================================================

def get_xml_text(element, tag_names):
    for tag in tag_names:
        found = element.find(tag)
        if found is not None and found.text:
            return found.text.strip()

    return ""


def extract_gdacs_coordinates(item):
    namespaces = {
        "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
        "georss": "http://www.georss.org/georss"
    }

    latitude = None
    longitude = None

    try:
        lat = item.find("geo:lat", namespaces)
        lon = item.find("geo:long", namespaces)

        if lat is not None and lon is not None:
            latitude = float(lat.text)
            longitude = float(lon.text)
            return latitude, longitude
    except Exception:
        pass

    try:
        point = item.find("georss:point", namespaces)

        if point is not None and point.text:
            values = point.text.strip().split()

            if len(values) >= 2:
                latitude = float(values[0])
                longitude = float(values[1])
                return latitude, longitude
    except Exception:
        pass

    try:
        point = item.find("point")

        if point is not None and point.text:
            values = point.text.strip().split()

            if len(values) >= 2:
                latitude = float(values[0])
                longitude = float(values[1])
                return latitude, longitude
    except Exception:
        pass

    return None, None


@st.cache_data(ttl=300, show_spinner=False)
def load_gdacs():
    response = requests.get(
        GDACS_RSS,
        timeout=25,
        headers={"User-Agent": "WorldDisasterLive/1.0"}
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)

    events = []

    for item in root.findall(".//item"):
        title = get_xml_text(item, ["title"])
        description = get_xml_text(item, ["description"])
        link = get_xml_text(item, ["link"])
        pub_date = get_xml_text(item, ["pubDate"])

        event_time = to_utc_datetime(pub_date)

        latitude, longitude = extract_gdacs_coordinates(item)

        combined_text = f"{title} {description}"
        hazard = classify_hazard(combined_text)

        if hazard == "Unknown":
            continue

        events.append({
            "id": link or title,
            "hazard": hazard,
            "title": title or "재난 경보",
            "description": description or "상세 설명이 제공되지 않았습니다.",
            "location": "GDACS 제공 위치 정보",
            "time": event_time,
            "latitude": latitude,
            "longitude": longitude,
            "magnitude": None,
            "source": "GDACS",
            "url": link or "https://www.gdacs.org/",
            "damage": "미확인"
        })

    return events


# =========================================================
# 데이터 합치기 및 필터링
# =========================================================

def get_event_key(event):
    source_id = event.get("id")

    if source_id:
        return f"{event.get('source')}:{source_id}"

    return (
        f"{event.get('source')}:"
        f"{event.get('title')}:"
        f"{event.get('time')}"
    )


def collect_events(start_date, end_date):
    events = []
    errors = []

    try:
        events.extend(load_usgs(start_date, end_date))
    except Exception as error:
        errors.append(f"USGS 데이터 수집 실패: {error}")

    try:
        events.extend(load_gdacs())
    except Exception as error:
        errors.append(f"GDACS 데이터 수집 실패: {error}")

    unique_events = {}
    for event in events:
        unique_events[get_event_key(event)] = event

    filtered = []

    start_dt = datetime.combine(start_date, time.min, tzinfo=UTC)
    end_dt = datetime.combine(
        end_date + timedelta(days=1),
        time.min,
        tzinfo=UTC
    )

    for event in unique_events.values():
        event_time = event.get("time")

        if event_time is None:
            continue

        if start_dt <= event_time < end_dt:
            filtered.append(event)

    filtered.sort(
        key=lambda event: event["time"],
        reverse=True
    )

    return filtered, errors


# =========================================================
# 사이드바
# =========================================================

st.sidebar.markdown("## 🌍 WORLD DISASTER LIVE")
st.sidebar.caption("GLOBAL DISASTER MONITORING")

st.sidebar.divider()

st.sidebar.markdown("### 재난 종류")

selected_hazard = st.sidebar.radio(
    "재난 분류",
    HAZARDS,
    format_func=lambda x: HAZARD_LABELS[x],
    label_visibility="collapsed"
)

st.sidebar.divider()

st.sidebar.markdown("### 조회 기간")

today_utc = datetime.now(UTC).date()

quick_period = st.sidebar.radio(
    "빠른 기간 선택",
    ["최근 7일", "오늘", "직접 선택"],
    index=0
)

if quick_period == "오늘":
    start_default = today_utc
    end_default = today_utc
elif quick_period == "최근 7일":
    start_default = today_utc - timedelta(days=6)
    end_default = today_utc
else:
    start_default = today_utc - timedelta(days=6)
    end_default = today_utc

start_date = st.sidebar.date_input(
    "시작 날짜",
    value=start_default,
    max_value=today_utc,
    key="start_date"
)

end_date = st.sidebar.date_input(
    "종료 날짜",
    value=end_default,
    max_value=today_utc,
    key="end_date"
)

if start_date > end_date:
    st.sidebar.error("시작 날짜가 종료 날짜보다 늦을 수 없습니다.")
    st.stop()

if (end_date - start_date).days > 365:
    st.sidebar.error("조회 기간은 최대 1년까지 선택할 수 있습니다.")
    st.stop()

if st.sidebar.button("↻ 데이터 새로고침", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()

st.sidebar.markdown("### 데이터 출처")
st.sidebar.markdown(
    "[USGS 지진 데이터](https://earthquake.usgs.gov/)"
)
st.sidebar.markdown(
    "[GDACS 재난 경보](https://www.gdacs.org/)"
)

st.sidebar.caption(
    "데이터 갱신 주기는 원본 기관의 제공 및 업데이트 주기에 따릅니다."
)


# =========================================================
# 상단 제목
# =========================================================

st.markdown(
    '<div class="main-title">WORLD DISASTER LIVE</div>',
    unsafe_allow_html=True
)
st.markdown(
    '<div class="sub-title">GLOBAL DISASTER MONITORING SYSTEM</div>',
    unsafe_allow_html=True
)

st.write("")
show_utc_clock()
st.write("")

st.divider()


# =========================================================
# Disease 전용 공식 정보 페이지
# =========================================================

if selected_hazard == "Disease":
    st.markdown("## 🦠 DISEASE INFORMATION")

    st.markdown("""
    <div class="notice">
        질병 발생 정보는 국가와 기관별로 발표 시점 및 집계 기준이 다릅니다.
        모든 국가의 감염병 발생 현황을 실시간으로 통합하는 공개 데이터는
        제공되지 않으므로, 확인되지 않은 사건이나 환자 수를 임의로 표시하지 않습니다.
        아래 공식 기관에서 확인된 최신 정보를 확인할 수 있습니다.
    </div>
    """, unsafe_allow_html=True)

    st.write("")

    col1, col2 = st.columns(2)

    for index, (name, url) in enumerate(OFFICIAL_SOURCES["Disease"]):
        target = col1 if index % 2 == 0 else col2

        with target:
            st.markdown(
                f"""
                <div class="source-box">
                    <div style="font-weight:700;color:#e2e8f0;">
                        🦠 {escape(name)}
                    </div>
                    <a href="{escape(url)}" target="_blank">
                        공식 자료 열기 ↗
                    </a>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.write("")
    st.markdown("### 대한민국 감염병 정보")

    for name, url in SOUTH_KOREA_SOURCES:
        st.markdown(f"- [{name}]({url})")

    st.info(
        "WHO Disease Outbreak News는 모든 국가의 모든 감염병 사례를 "
        "빠짐없이 수록하는 목록이 아닙니다."
    )

    st.stop()


# =========================================================
# 데이터 불러오기
# =========================================================

with st.spinner("공개 재난 데이터를 불러오는 중입니다..."):
    all_events, load_errors = collect_events(start_date, end_date)


# =========================================================
# 재난 분류 필터
# =========================================================

if selected_hazard == "All":
    visible_events = all_events
else:
    visible_events = [
        event for event in all_events
        if event["hazard"] == selected_hazard
    ]


# =========================================================
# 상단 통계
# =========================================================

total_count = len(all_events)
visible_count = len(visible_events)

earthquake_count = sum(
    1 for event in all_events
    if event["hazard"] == "Earthquake"
)

gdacs_count = sum(
    1 for event in all_events
    if event["source"] == "GDACS"
)

metric1, metric2, metric3, metric4 = st.columns(4)

metrics = [
    ("전체 수집 사건", total_count),
    ("현재 분류 사건", visible_count),
    ("지진 사건", earthquake_count),
    ("GDACS 경보", gdacs_count)
]

for column, (label, value) in zip(
    [metric1, metric2, metric3, metric4],
    metrics
):
    with column:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value:,}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

st.write("")

if load_errors:
    with st.expander("데이터 수집 상태 확인"):
        for error in load_errors:
            st.warning(error)

st.markdown(
    f'<div class="section-title">EVENT LIST · {HAZARD_LABELS[selected_hazard]}</div>',
    unsafe_allow_html=True
)


# =========================================================
# 사건이 없는 경우
# =========================================================

if not visible_events:
    st.info(
        "선택한 기간과 분류에서 표시할 사건을 찾지 못했습니다. "
        "원본 기관에 데이터가 없거나 해당 분류의 정보가 제공되지 않을 수 있습니다."
    )


# =========================================================
# 사건 카드
# =========================================================

for index, event in enumerate(visible_events):
    hazard = event["hazard"]
    emoji = HAZARD_EMOJI.get(hazard, "⚠️")

    event_time = event["time"]

    if event_time:
        time_text = event_time.strftime("%Y-%m-%d %H:%M UTC")
    else:
        time_text = "발생 시각 미확인"

    title = escape(str(event["title"]))
    description = escape(str(event["description"]))
    source = escape(str(event["source"]))

    magnitude_text = ""
    if event.get("magnitude") is not None:
        magnitude_text = f" · 규모 M {event['magnitude']:.1f}"

    left, right = st.columns([5, 1])

    with left:
        st.markdown(
            f"""
            <div class="event-card">
                <div class="event-type">
                    {emoji} {escape(HAZARD_LABELS.get(hazard, hazard))}
                    &nbsp; | &nbsp; {source}
                </div>
                <div class="event-title">{title}</div>
                <div class="event-info">
                    📍 {escape(str(event["location"]))}<br>
                    🕒 {time_text}{magnitude_text}<br>
                    피해 통계: 미확인
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with right:
        st.write("")
        st.markdown(
            f'<a href="{escape(str(event["url"]))}" target="_blank">'
            f'<span style="font-size:13px;">원본 자료 ↗</span></a>',
            unsafe_allow_html=True
        )

    with st.expander("상세 정보 보기"):
        st.markdown(f"**재난 종류:** {HAZARD_LABELS.get(hazard, hazard)}")
        st.markdown(f"**사건명:** {event['title']}")
        st.markdown(f"**설명:** {event['description']}")
        st.markdown(f"**출처:** {event['source']}")
        st.markdown(f"**발생 시각:** {time_text}")

        if event.get("magnitude") is not None:
            st.markdown(
                f"**지진 규모:** M {event['magnitude']:.1f}"
            )

        latitude = event.get("latitude")
        longitude = event.get("longitude")

        if latitude is not None and longitude is not None:
            st.markdown(
                f"**위도:** {latitude:.4f} / "
                f"**경도:** {longitude:.4f}"
            )

            map_df = pd.DataFrame({
                "lat": [latitude],
                "lon": [longitude]
            })

            st.map(map_df, zoom=5)

        else:
            st.caption("이 사건은 지도 좌표가 제공되지 않았습니다.")

        st.markdown(
            f"[원본 기관 자료 확인하기]({event['url']})"
        )

    st.write("")


# =========================================================
# 전체 사건 지도
# =========================================================

st.divider()
st.markdown("## 🗺️ GLOBAL EVENT MAP")

map_events = []

for event in visible_events:
    latitude = event.get("latitude")
    longitude = event.get("longitude")

    if latitude is None or longitude is None:
        continue

    map_events.append({
        "lat": latitude,
        "lon": longitude
    })

if map_events:
    map_df = pd.DataFrame(map_events)

    st.map(
        map_df,
        zoom=None,
        use_container_width=True
    )

    st.caption(
        f"지도에 표시된 사건: {len(map_events)}건 "
        "/ 좌표가 제공된 사건만 표시합니다."
    )
else:
    st.info(
        "현재 선택한 분류에서 지도에 표시할 수 있는 좌표 정보가 없습니다."
    )


# =========================================================
# 공식 기관 정보
# =========================================================

st.divider()
st.markdown("## 🌐 OFFICIAL INFORMATION")

if selected_hazard == "All":
    source_groups = OFFICIAL_SOURCES
else:
    source_groups = {
        selected_hazard: OFFICIAL_SOURCES.get(selected_hazard, [])
    }

for group_name, sources in source_groups.items():
    if not sources:
        continue

    with st.expander(
        f"{HAZARD_LABELS.get(group_name, group_name)} 공식 기관"
    ):
        for name, url in sources:
            st.markdown(f"- [{name}]({url})")


# =========================================================
# 하단 안내
# =========================================================

st.divider()

st.markdown("""
<div style="text-align:center;color:#64748b;font-size:11px;line-height:2;">
    WORLD DISASTER LIVE<br>
    DATA SOURCES: USGS · GDACS · OFFICIAL GOVERNMENT AGENCIES<br>
    피해 통계는 공식 출처에서 확인되지 않으면 표시하지 않습니다.<br>
    본 대시보드는 재난 정보 확인을 위한 참고용 서비스입니다.
</div>
""", unsafe_allow_html=True)
