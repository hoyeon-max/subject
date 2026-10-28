# main.py
import re
import html
import time
import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import xml.etree.ElementTree as ET

from datetime import datetime, date, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

# =========================================================
# 기본 설정
# =========================================================
st.set_page_config(
    page_title="WORLD DISASTER LIVE",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BG = "#0f172a"
PANEL = "#172238"
BORDER = "#334155"
TEXT = "#e2e8f0"
MUTED = "#94a3b8"
ACCENT = "#38bdf8"

UTC = timezone.utc

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
GDACS_URL = "https://www.gdacs.org/xml/rss.xml"
NEWS_URL = "https://news.google.com/rss/search"

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

HAZARD_KO = {
    "All": "전체 재난",
    "Typhoon": "태풍",
    "Earthquake": "지진",
    "Wildfire": "산불",
    "Flood": "홍수",
    "Heavy Rain": "폭우",
    "Drought": "가뭄",
    "Heavy Snow": "폭설",
    "Heatwave": "폭염",
    "Cold Wave": "한파",
    "Landslide": "산사태",
}

SORT_OPTIONS = [
    "최신순",
    "사상자순",
    "재산피해순",
    "기간순",
    "지진 규모순",
    "태풍 강도순",
]

# =========================================================
# CSS
# =========================================================
st.markdown(
    f"""
    <style>
    .stApp {{
        background: {BG};
        color: {TEXT};
    }}
    header[data-testid="stHeader"] {{
        background: {BG};
    }}
    section[data-testid="stSidebar"] {{
        background: {BG};
    }}
    h1, h2, h3, h4, p, label, span, div {{
        color: inherit;
    }}
    .block-container {{
        padding-top: 1rem;
        padding-bottom: 3rem;
        max-width: 1600px;
    }}
    .main-title {{
        text-align: center;
        font-size: 2.6rem;
        font-weight: 900;
        letter-spacing: 0.12rem;
        color: #f8fafc;
        margin: 0.2rem 0 0.2rem 0;
    }}
    .subtitle {{
        text-align: center;
        color: {MUTED};
        font-size: 0.95rem;
        margin-bottom: 1rem;
    }}
    .section-title {{
        font-size: 1.15rem;
        font-weight: 800;
        color: #f8fafc;
        margin: 1.2rem 0 0.65rem 0;
    }}
    .event-card, .news-card {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 14px;
        padding: 1rem;
        margin-bottom: 0.8rem;
        min-height: 150px;
    }}
    .event-title {{
        font-size: 1.03rem;
        font-weight: 800;
        line-height: 1.45;
        color: #f8fafc;
        overflow-wrap: anywhere;
    }}
    .event-meta {{
        color: {MUTED};
        font-size: 0.86rem;
        margin-top: 0.45rem;
        line-height: 1.65;
    }}
    .metric-card {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 12px;
        padding: 0.8rem;
        text-align: center;
        min-height: 90px;
    }}
    .metric-label {{
        color: {MUTED};
        font-size: 0.85rem;
    }}
    .metric-value {{
        color: #f8fafc;
        font-size: 1.35rem;
        font-weight: 800;
        margin-top: 0.3rem;
    }}
    div.stButton > button {{
        border-radius: 9px;
        border: 1px solid {BORDER};
        background: {PANEL};
        color: {TEXT};
        font-weight: 700;
        min-height: 2.5rem;
    }}
    div.stButton > button:hover {{
        border-color: {ACCENT};
        color: #7dd3fc;
    }}
    div[data-testid="stSelectbox"] > label,
    div[data-testid="stDateInput"] > label {{
        color: {TEXT};
        font-weight: 700;
    }}
    a {{
        color: #7dd3fc !important;
    }}
    hr {{
        border-color: {BORDER};
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# 시간과 문자열 유틸리티
# =========================================================
def utc_now():
    return datetime.now(UTC)


def to_utc_datetime(value):
    """문자열 또는 datetime을 UTC datetime으로 변환."""
    if not value:
        return None

    try:
        if isinstance(value, datetime):
            dt = value
        else:
            text = str(value).strip()
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        return dt.astimezone(UTC)
    except (ValueError, TypeError, OverflowError):
        return None


def parse_rss_date(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except (ValueError, TypeError, OverflowError):
        return to_utc_datetime(value)


def fmt_time(value):
    dt = to_utc_datetime(value)
    if not dt:
        return "시간 미확인"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def safe_text(value):
    if value is None:
        return ""
    return html.unescape(re.sub(r"<[^>]*>", " ", str(value))).strip()


def get_tag_text(element, tag_names):
    """XML에서 네임스페이스 여부와 관계없이 태그 이름을 찾음."""
    wanted = {x.lower() for x in tag_names}

    for child in element.iter():
        local_name = child.tag.split("}")[-1].lower()
        if local_name in wanted and child.text:
            value = child.text.strip()
            if value:
                return value

    return ""


def parse_number(value):
    if value is None:
        return None
    try:
        match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
        return float(match.group(0)) if match else None
    except (ValueError, TypeError):
        return None


def compact_number(value):
    if value is None:
        return "미확인"
    return f"{value:,.0f}"


def parse_duration_days(text):
    """
    설명에 기간이 명시된 경우에만 기간을 추출.
    명시되지 않은 기간을 임의로 추정하지 않음.
    """
    text = safe_text(text).lower()

    patterns = [
        r"\b(\d+(?:\.\d+)?)\s*days?\b",
        r"\b(\d+(?:\.\d+)?)\s*hours?\b",
        r"\b(\d+(?:\.\d+)?)\s*weeks?\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            amount = float(match.group(1))
            if "hour" in pattern:
                return amount / 24
            if "week" in pattern:
                return amount * 7
            return amount

    return None


def parse_casualties(text):
    """
    공개된 설명에서 명시적인 사망·부상 숫자만 추출.
    각 항목이 확인되지 않으면 None으로 둠.
    """
    text = safe_text(text).lower()

    fatal_patterns = [
        r"\b(\d[\d,]*)\s+(?:people\s+)?(?:were\s+)?killed\b",
        r"\b(\d[\d,]*)\s+fatalities\b",
        r"\bdeaths?\s*:\s*(\d[\d,]*)\b",
        r"\b(\d[\d,]*)\s+deaths?\b",
    ]
    injured_patterns = [
        r"\b(\d[\d,]*)\s+(?:people\s+)?injured\b",
        r"\b(\d[\d,]*)\s+wounded\b",
        r"\binjured\s*:\s*(\d[\d,]*)\b",
    ]

    def first_match(patterns):
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return int(match.group(1).replace(",", ""))
                except ValueError:
                    pass
        return None

    deaths = first_match(fatal_patterns)
    injured = first_match(injured_patterns)

    if deaths is None and injured is None:
        return None

    return (deaths or 0) + (injured or 0)


def parse_damage_amount(text):
    """
    USD 재산 피해액이 명시된 경우에만 추출.
    원문에 명시된 달러 단위를 기준으로 환산.
    """
    text = safe_text(text).lower()

    patterns = [
        r"(?:damage|losses|economic losses|property damage)"
        r"[^.]{0,50}?\$\s*(\d+(?:\.\d+)?)\s*(billion|million|thousand|bn|mn|m|b)?",
        r"\$\s*(\d+(?:\.\d+)?)\s*(billion|million|thousand|bn|mn|m|b)"
        r"[^.]{0,40}?(?:damage|losses|damages)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue

        amount = float(match.group(1))
        unit = (match.group(2) or "").lower()

        if unit in ("billion", "bn", "b"):
            amount *= 1_000_000_000
        elif unit in ("million", "mn", "m"):
            amount *= 1_000_000
        elif unit == "thousand":
            amount *= 1_000

        return amount

    return None


def parse_magnitude(text):
    patterns = [
        r"\b(?:magnitude|mag)\s*(?:of|:|=)?\s*(\d+(?:\.\d+)?)",
        r"\bmw\s*(\d+(?:\.\d+)?)",
    ]
    text = safe_text(text).lower()

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))

    return None


def parse_wind_kmh(text):
    """
    풍속이 수치와 단위로 명시된 경우 km/h로 통일.
    숫자만 있거나 단위가 없으면 추정하지 않음.
    """
    text = safe_text(text).lower()

    patterns = [
        (r"\b(\d+(?:\.\d+)?)\s*km/h\b", 1.0),
        (r"\b(\d+(?:\.\d+)?)\s*kph\b", 1.0),
        (r"\b(\d+(?:\.\d+)?)\s*mph\b", 1.60934),
        (r"\b(\d+(?:\.\d+)?)\s*knots?\b", 1.852),
        (r"\b(\d+(?:\.\d+)?)\s*kt\b", 1.852),
    ]

    for pattern, factor in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1)) * factor

    return None


def parse_typhoon_category(text):
    text = safe_text(text).lower()

    # Category 1–5 등 공식 범주가 명시된 경우만 사용
    match = re.search(r"\bcategory\s*([1-5])\b", text)
    if match:
        return int(match.group(1))

    match = re.search(r"\b(cat)\s*([1-5])\b", text)
    if match:
        return int(match.group(2))

    # 풍속은 category가 아닌 별도 수치로 보관
    return None


def identify_hazard(title, description="", category=""):
    text = f"{title} {description} {category}".lower()

    if any(x in text for x in ["earthquake", "seismic", "地震"]):
        return "Earthquake"
    if any(x in text for x in ["typhoon", "hurricane", "cyclone", "tropical storm"]):
        return "Typhoon"
    if any(x in text for x in ["wildfire", "forest fire", "bushfire"]):
        return "Wildfire"
    if any(x in text for x in ["landslide", "mudslide"]):
        return "Landslide"
    if any(x in text for x in ["drought"]):
        return "Drought"
    if any(x in text for x in ["heavy snow", "snowstorm", "blizzard"]):
        return "Heavy Snow"
    if any(x in text for x in ["heatwave", "heat wave", "extreme heat"]):
        return "Heatwave"
    if any(x in text for x in ["cold wave", "coldwave", "extreme cold"]):
        return "Cold Wave"
    if any(x in text for x in ["flood", "flash flood", "inundation"]):
        return "Flood"
    if any(x in text for x in ["heavy rain", "extreme rainfall", "rainstorm"]):
        return "Heavy Rain"

    return "Other"


def hazard_ko(hazard):
    return HAZARD_KO.get(hazard, "기타 재난")


def make_event(
    event_id,
    title,
    hazard,
    location,
    event_time,
    description="",
    source_url="",
    source="",
    latitude=None,
    longitude=None,
    magnitude=None,
    fatalities=None,
    injured=None,
    property_damage=None,
    duration_days=None,
    wind_kmh=None,
    typhoon_category=None,
    end_time=None,
):
    description = safe_text(description)
    combined = f"{title} {description}"

    casualties = None
    if fatalities is not None or injured is not None:
        casualties = (fatalities or 0) + (injured or 0)
    else:
        casualties = parse_casualties(combined)

    if property_damage is None:
        property_damage = parse_damage_amount(combined)

    if magnitude is None and hazard == "Earthquake":
        magnitude = parse_magnitude(combined)

    if wind_kmh is None and hazard == "Typhoon":
        wind_kmh = parse_wind_kmh(combined)

    if typhoon_category is None and hazard == "Typhoon":
        typhoon_category = parse_typhoon_category(combined)

    start_dt = to_utc_datetime(event_time)
    end_dt = to_utc_datetime(end_time)

    if duration_days is None and start_dt and end_dt and end_dt >= start_dt:
        duration_days = (end_dt - start_dt).total_seconds() / 86400

    if duration_days is None:
        duration_days = parse_duration_days(combined)

    return {
        "id": str(event_id),
        "title": safe_text(title) or "제목 미확인",
        "hazard": hazard,
        "location": safe_text(location) or "지역 미확인",
        "time": start_dt,
        "end_time": end_dt,
        "description": description,
        "source_url": source_url or "",
        "source": source or "",
        "latitude": parse_number(latitude),
        "longitude": parse_number(longitude),
        "magnitude": parse_number(magnitude),
        "casualties": casualties,
        "property_damage": parse_number(property_damage),
        "duration_days": parse_number(duration_days),
        "wind_kmh": parse_number(wind_kmh),
        "typhoon_category": parse_number(typhoon_category),
    }


# =========================================================
# UTC 시계
# =========================================================
def render_utc_header():
    components.html(
        """
        <div style="
            position:relative;
            font-family:Arial,sans-serif;
            background:#0f172a;
            color:#f8fafc;
            padding:4px 0 10px 0;
            text-align:center;
        ">
          <div id="clock" style="
            font-size:clamp(42px,7vw,76px);
            font-weight:900;
            letter-spacing:2px;
            line-height:1.1;
          ">--:--:--</div>
          <div style="
            color:#94a3b8;
            font-size:13px;
            letter-spacing:3px;
            margin-top:3px;
          ">UTC</div>
          <div id="clockdate" style="
            position:absolute;
            right:5px;
            top:8px;
            color:#94a3b8;
            font-size:12px;
            text-align:right;
          ">----</div>
        </div>
        <script>
          function tick() {
            const now = new Date();
            const opts = {
              timeZone: "UTC",
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
              hour12: false
            };
            document.getElementById("clock").textContent =
              new Intl.DateTimeFormat("en-GB", opts).format(now);
            document.getElementById("clockdate").textContent =
              new Intl.DateTimeFormat("en-GB", {
                timeZone:"UTC",
                year:"numeric",
                month:"short",
                day:"2-digit"
              }).format(now) + " UTC";
          }
          tick();
          setInterval(tick, 1000);
        </script>
        """,
        height=120,
        scrolling=False,
    )


# =========================================================
# 날짜 필터
# =========================================================
def initialize_period():
    today = utc_now().date()

    if "period_start" not in st.session_state:
        st.session_state.period_start = today - timedelta(days=6)
    if "period_end" not in st.session_state:
        st.session_state.period_end = today

    if "period_start_input" not in st.session_state:
        st.session_state.period_start_input = st.session_state.period_start
    if "period_end_input" not in st.session_state:
        st.session_state.period_end_input = st.session_state.period_end


def render_period_selector():
    initialize_period()

    st.markdown('<div class="section-title">Date Range (UTC)</div>', unsafe_allow_html=True)

    today = utc_now().date()

    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])

    with c1:
        start_date = st.date_input(
            "시작 날짜",
            key="period_start_input",
            min_value=date(2000, 1, 1),
            max_value=today,
        )

    with c2:
        end_date = st.date_input(
            "종료 날짜",
            key="period_end_input",
            min_value=date(2000, 1, 1),
            max_value=today,
        )

    with c3:
        if st.button("Apply Period", use_container_width=True):
            if start_date > end_date:
                st.error("시작 날짜는 종료 날짜보다 늦을 수 없습니다.")
            else:
                st.session_state.period_start = start_date
                st.session_state.period_end = end_date
                st.rerun()

    with c4:
        if st.button("Last 7 Days", use_container_width=True):
            st.session_state.period_start = today - timedelta(days=6)
            st.session_state.period_end = today
            st.session_state.period_start_input = today - timedelta(days=6)
            st.session_state.period_end_input = today
            st.rerun()

    if st.session_state.period_start > st.session_state.period_end:
        st.warning("시작 날짜와 종료 날짜를 확인해 주세요.")
        return None, None

    start_dt = datetime.combine(
        st.session_state.period_start, datetime.min.time(), tzinfo=UTC
    )
    end_dt = datetime.combine(
        st.session_state.period_end + timedelta(days=1),
        datetime.min.time(),
        tzinfo=UTC,
    )

    st.caption(
        f"선택 기간: {start_dt:%Y-%m-%d} 00:00 UTC "
        f"~ {st.session_state.period_end:%Y-%m-%d} 23:59 UTC"
    )

    return start_dt, end_dt


def is_in_period(dt, start_dt, end_dt):
    dt = to_utc_datetime(dt)
    return bool(dt and start_dt and end_dt and start_dt <= dt < end_dt)


# =========================================================
# USGS 지진 데이터
# =========================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_earthquakes(start_iso, end_iso):
    params = {
        "format": "geojson",
        "starttime": start_iso,
        "endtime": end_iso,
        "orderby": "time",
        "limit": 1000,
    }

    response = requests.get(
        USGS_URL,
        params=params,
        timeout=25,
        headers={"User-Agent": "WorldDisasterLive/1.0"},
    )
    response.raise_for_status()
    payload = response.json()

    events = []
    for feature in payload.get("features", []):
        props = feature.get("properties", {}) or {}
        geometry = feature.get("geometry", {}) or {}
        coords = geometry.get("coordinates", []) or []

        magnitude = props.get("mag")
        place = props.get("place") or "지역 미확인"

        timestamp = props.get("time")
        event_time = None
        if timestamp is not None:
            event_time = datetime.fromtimestamp(timestamp / 1000, tz=UTC)

        longitude = coords[0] if len(coords) > 0 else None
        latitude = coords[1] if len(coords) > 1 else None

        title = props.get("title") or (
            f"M{magnitude} earthquake - {place}"
            if magnitude is not None
            else f"Earthquake - {place}"
        )

        events.append(
            make_event(
                event_id=feature.get("id") or props.get("code") or title,
                title=title,
                hazard="Earthquake",
                location=place,
                event_time=event_time,
                description=props.get("alert") or "",
                source_url=props.get("url") or "",
                source="USGS",
                latitude=latitude,
                longitude=longitude,
                magnitude=magnitude,
            )
        )

    return events


# =========================================================
# GDACS RSS 재난 데이터
# =========================================================
@st.cache_data(ttl=600, show_spinner=False)
def load_gdacs_events():
    response = requests.get(
        GDACS_URL,
        timeout=25,
        headers={"User-Agent": "WorldDisasterLive/1.0"},
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)
    events = []

    for item in root.iter():
        if item.tag.split("}")[-1].lower() != "item":
            continue

        title = get_tag_text(item, ["title"])
        description = get_tag_text(item, ["description", "summary"])
        link = get_tag_text(item, ["link"])
        guid = get_tag_text(item, ["guid"])
        pub_date = get_tag_text(item, ["pubDate", "published", "updated"])
        category = get_tag_text(item, ["category", "eventtype", "eventType"])

        event_time = parse_rss_date(pub_date)
        hazard = identify_hazard(title, description, category)

        # RSS 내의 시작·종료 시각이 제공될 때만 지속 기간 계산
        start_text = get_tag_text(
            item, ["fromdate", "fromDate", "eventstart", "starttime", "startTime"]
        )
        end_text = get_tag_text(
            item, ["todate", "toDate", "eventend", "endtime", "endTime"]
        )
        start_time = to_utc_datetime(start_text) or event_time
        end_time = to_utc_datetime(end_text)

        # 위치 문자열은 원문에 명시된 값만 사용
        location = get_tag_text(item, ["location", "country", "area"])
        if not location:
            location = title

        latitude = get_tag_text(item, ["lat", "latitude"])
        longitude = get_tag_text(item, ["lon", "long", "longitude"])

        event_id = guid or link or f"{title}-{pub_date}"

        events.append(
            make_event(
                event_id=event_id,
                title=title,
                hazard=hazard,
                location=location,
                event_time=start_time,
                end_time=end_time,
                description=description,
                source_url=link,
                source="GDACS",
                latitude=latitude,
                longitude=longitude,
            )
        )

    # RSS에 중복 항목이 있을 경우 ID로 중복 제거
    unique = {}
    for event in events:
        unique[event["id"]] = event

    return list(unique.values())


# =========================================================
# Google News RSS
# =========================================================
@st.cache_data(ttl=600, show_spinner=False)
def load_news(hazard, start_date_iso, end_date_iso):
    query_terms = {
        "All": "natural disaster",
        "Typhoon": "typhoon OR hurricane OR cyclone",
        "Earthquake": "earthquake",
        "Wildfire": "wildfire",
        "Flood": "flood",
        "Heavy Rain": '"heavy rain" OR extreme rainfall',
        "Drought": "drought",
        "Heavy Snow": '"heavy snow" OR blizzard',
        "Heatwave": "heatwave OR extreme heat",
        "Cold Wave": '"cold wave" OR extreme cold',
        "Landslide": "landslide OR mudslide",
    }

    start_date = date.fromisoformat(start_date_iso)
    end_date = date.fromisoformat(end_date_iso)

    # Google News의 after/before는 일반적으로 종료일을 배타적으로 취급
    query = (
        f"{query_terms.get(hazard, 'natural disaster')} "
        f"after:{start_date.isoformat()} "
        f"before:{(end_date + timedelta(days=1)).isoformat()}"
    )

    params = {
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }

    response = requests.get(
        NEWS_URL,
        params=params,
        timeout=25,
        headers={"User-Agent": "WorldDisasterLive/1.0"},
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)
    articles = []

    for item in root.iter():
        if item.tag.split("}")[-1].lower() != "item":
            continue

        title = get_tag_text(item, ["title"])
        link = get_tag_text(item, ["link"])
        pub_date = get_tag_text(item, ["pubDate", "published"])
        description = get_tag_text(item, ["description", "summary"])
        source = get_tag_text(item, ["source"])

        published = parse_rss_date(pub_date)

        if not published:
            continue
        if not is_in_period(
            published,
            datetime.combine(start_date, datetime.min.time(), tzinfo=UTC),
            datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=UTC),
        ):
            continue

        articles.append(
            {
                "title": safe_text(title),
                "url": link,
                "published": published,
                "description": safe_text(description),
                "source": safe_text(source) or "Google News",
            }
        )

    # URL 중복 제거
    unique = {}
    for article in articles:
        unique[article["url"] or article["title"]] = article

    return list(unique.values())


# =========================================================
# 정렬 처리
# =========================================================
def known_first_sort(items, key, reverse=True):
    """
    값이 확인된 항목을 먼저 정렬하고 미확인 항목은 뒤에 배치.
    """
    known = [x for x in items if x.get(key) is not None]
    unknown = [x for x in items if x.get(key) is None]

    known.sort(key=lambda x: x.get(key), reverse=reverse)

    # 미확인 항목도 최신순으로 정리
    unknown.sort(
        key=lambda x: x.get("time") or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )

    return known + unknown


def sort_events(events, criterion):
    if criterion == "최신순":
        return sorted(
            events,
            key=lambda x: x.get("time") or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )

    if criterion == "사상자순":
        return known_first_sort(events, "casualties", reverse=True)

    if criterion == "재산피해순":
        return known_first_sort(events, "property_damage", reverse=True)

    if criterion == "기간순":
        return known_first_sort(events, "duration_days", reverse=True)

    if criterion == "지진 규모순":
        earthquakes = [x for x in events if x["hazard"] == "Earthquake"]
        others = [x for x in events if x["hazard"] != "Earthquake"]

        earthquakes = known_first_sort(earthquakes, "magnitude", reverse=True)
        others.sort(
            key=lambda x: x.get("time") or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return earthquakes + others

    if criterion == "태풍 강도순":
        typhoons = [x for x in events if x["hazard"] == "Typhoon"]
        others = [x for x in events if x["hazard"] != "Typhoon"]

        # 태풍은 공식 범주가 있으면 우선 비교하고,
        # 범주가 없으면 풍속이 확인된 항목을 비교
        typhoons.sort(
            key=lambda x: (
                x.get("typhoon_category") is not None,
                x.get("typhoon_category") or -1,
                x.get("wind_kmh") is not None,
                x.get("wind_kmh") or -1,
                x.get("time") or datetime.min.replace(tzinfo=UTC),
            ),
            reverse=True,
        )
        others.sort(
            key=lambda x: x.get("time") or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return typhoons + others

    return events


# =========================================================
# 카드와 상세 팝업
# =========================================================
def show_value(value, suffix=""):
    if value is None:
        return "미확인"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,}{suffix}" if isinstance(value, (int, float)) else f"{value}{suffix}"


def event_detail(event):
    @st.dialog("Disaster Details", width="large")
    def _detail():
        st.markdown(f"### {event['title']}")
        st.caption(
            f"{hazard_ko(event['hazard'])} · "
            f"{event['location']} · "
            f"{fmt_time(event['time'])}"
        )

        st.markdown("---")

        a, b, c = st.columns(3)
        with a:
            st.metric("사상자", show_value(event.get("casualties"), "명"))
        with b:
            st.metric(
                "재산 피해",
                (
                    f"${event['property_damage']:,.0f}"
                    if event.get("property_damage") is not None
                    else "미확인"
                ),
            )
        with c:
            st.metric("지속 기간", show_value(event.get("duration_days"), "일"))

        if event["hazard"] == "Earthquake":
            st.metric("지진 규모", show_value(event.get("magnitude")))

        if event["hazard"] == "Typhoon":
            x, y = st.columns(2)
            with x:
                st.metric(
                    "태풍 범주",
                    (
                        f"Category {int(event['typhoon_category'])}"
                        if event.get("typhoon_category") is not None
                        else "미확인"
                    ),
                )
            with y:
                st.metric("풍속", show_value(event.get("wind_kmh"), " km/h"))

        st.markdown("#### 상세 설명")
        if event.get("description"):
            st.write(event["description"])
        else:
            st.info("제공된 상세 설명이 없습니다.")

        lat = event.get("latitude")
        lon = event.get("longitude")

        if lat is not None and lon is not None:
            st.markdown("#### 위치")
            st.write(f"위도: {lat} · 경도: {lon}")
            map_url = f"https://www.google.com/maps?q={lat},{lon}"
            st.link_button("지도에서 위치 보기", map_url, use_container_width=True)
        else:
            st.caption("좌표 정보는 제공되지 않았습니다.")

        st.markdown("#### 출처")
        st.write(event.get("source") or "출처 미확인")
        if event.get("source_url"):
            st.link_button(
                "원문 / 공식 출처 열기",
                event["source_url"],
                use_container_width=True,
            )

    _detail()


def render_event_card(event, index):
    title = event.get("title") or "제목 미확인"
    location = event.get("location") or "지역 미확인"
    hazard_label = hazard_ko(event.get("hazard", "Other"))

    if event.get("hazard") == "Earthquake":
        strength = f" · M{event['magnitude']}" if event.get("magnitude") is not None else ""
    elif event.get("hazard") == "Typhoon":
        if event.get("typhoon_category") is not None:
            strength = f" · Category {int(event['typhoon_category'])}"
        elif event.get("wind_kmh") is not None:
            strength = f" · {event['wind_kmh']:.0f} km/h"
        else:
            strength = ""
    else:
        strength = ""

    casualties_text = show_value(event.get("casualties"), "명")
    damage_text = (
        f"${event['property_damage']:,.0f}"
        if event.get("property_damage") is not None
        else "미확인"
    )

    st.markdown(
        f"""
        <div class="event-card">
          <div class="event-title">{html.escape(title)}</div>
          <div class="event-meta">
            {html.escape(hazard_label)}{html.escape(strength)}<br>
            {html.escape(location)}<br>
            {html.escape(fmt_time(event.get("time")))}<br>
            사상자: {html.escape(casualties_text)}
            &nbsp; | &nbsp; 재산 피해: {html.escape(damage_text)}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("View Details", key=f"event_detail_{index}_{event['id']}", use_container_width=True):
        event_detail(event)


def render_news_card(article, index):
    title = article.get("title") or "제목 미확인"
    source = article.get("source") or "Google News"

    st.markdown(
        f"""
        <div class="news-card">
          <div class="event-title">{html.escape(title)}</div>
          <div class="event-meta">
            {html.escape(source)}<br>
            {html.escape(fmt_time(article.get("published")))}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if article.get("url"):
        st.link_button(
            "기사 열기",
            article["url"],
            key=f"news_open_{index}",
            use_container_width=True,
        )


# =========================================================
# 메인 UI
# =========================================================
render_utc_header()

st.markdown(
    '<div class="main-title">WORLD DISASTER LIVE</div>'
    '<div class="subtitle">Global Disaster Monitoring Dashboard · UTC</div>',
    unsafe_allow_html=True,
)

top1, top2 = st.columns([4, 1])
with top1:
    st.markdown(
        '<div class="section-title">Hazard Categories</div>',
        unsafe_allow_html=True,
    )
with top2:
    if st.button("Refresh Data", use_container_width=True):
        load_earthquakes.clear()
        load_gdacs_events.clear()
        load_news.clear()
        st.rerun()

# 재난 종류 메뉴: 6개 + 5개
if "hazard" not in st.session_state:
    st.session_state.hazard = "All"

for row_hazards in (HAZARDS[:6], HAZARDS[6:]):
    cols = st.columns(len(row_hazards))
    for col, hazard_name in zip(cols, row_hazards):
        with col:
            selected = st.session_state.hazard == hazard_name
            button_label = f"✓ {hazard_name}" if selected else hazard_name
            if st.button(
                button_label,
                key=f"hazard_{hazard_name}",
                use_container_width=True,
            ):
                st.session_state.hazard = hazard_name
                st.rerun()

start_dt, end_dt = render_period_selector()

if start_dt is None or end_dt is None:
    st.stop()

st.markdown(
    '<div class="section-title">Sorting Criteria</div>',
    unsafe_allow_html=True,
)

sort_col1, sort_col2 = st.columns([2, 3])

with sort_col1:
    sort_criterion = st.selectbox(
        "재난 카드 정렬 기준",
        SORT_OPTIONS,
        index=0,
        help=(
            "사상자·재산 피해·기간은 확인된 값이 있는 사건을 먼저 표시합니다. "
            "지진 규모순은 지진을, 태풍 강도순은 태풍을 먼저 비교합니다."
        ),
    )

with sort_col2:
    st.caption(
        "사상자순 · 재산피해순 · 기간순은 확인된 수치만 비교합니다. "
        "지진 규모순은 지진을, 태풍 강도순은 태풍을 우선 표시합니다. "
        "미확인 값은 임의로 계산하지 않습니다."
    )

# 데이터 로드
all_events = []
news_items = []
errors = []

start_iso = start_dt.isoformat().replace("+00:00", "Z")
end_iso = end_dt.isoformat().replace("+00:00", "Z")

with st.spinner("재난 데이터를 불러오는 중입니다..."):
    try:
        all_events.extend(load_earthquakes(start_iso, end_iso))
    except Exception as exc:
        errors.append(f"USGS 지진 데이터: {exc}")

    try:
        gdacs_events = load_gdacs_events()
        all_events.extend(
            [
                event for event in gdacs_events
                if is_in_period(event.get("time"), start_dt, end_dt)
            ]
        )
    except Exception as exc:
        errors.append(f"GDACS 재난 데이터: {exc}")

    try:
        news_items = load_news(
            st.session_state.hazard,
            st.session_state.period_start.isoformat(),
            st.session_state.period_end.isoformat(),
        )
    except Exception as exc:
        errors.append(f"Google News: {exc}")

# 중복 지진 제거
deduped = {}
for event in all_events:
    deduped[event["id"]] = event
all_events = list(deduped.values())

# 선택한 기간과 재난 종류로 필터링
if st.session_state.hazard != "All":
    filtered_events = [
        event for event in all_events
        if event.get("hazard") == st.session_state.hazard
    ]
else:
    filtered_events = all_events

filtered_news = news_items

# 정렬 기준 적용
filtered_events = sort_events(filtered_events, sort_criterion)
filtered_news.sort(
    key=lambda item: item.get("published") or datetime.min.replace(tzinfo=UTC),
    reverse=True,
)

# 오류가 있으면 숨기지 않고 표시
if errors:
    with st.expander("일부 데이터 출처에 연결할 수 없습니다", expanded=False):
        for error in errors:
            st.warning(error)
        st.caption(
            "일시적인 네트워크 오류 또는 출처 서비스 제한일 수 있습니다. "
            "새로고침을 눌러 다시 시도해 주세요."
        )

# 상단 지표
st.markdown(
    '<div class="section-title">Overview</div>',
    unsafe_allow_html=True,
)

total_events = len(filtered_events)
earthquake_count = sum(x["hazard"] == "Earthquake" for x in filtered_events)
typhoon_count = sum(x["hazard"] == "Typhoon" for x in filtered_events)
news_count = len(filtered_news)

metric_cols = st.columns(4)
metrics = [
    ("재난 이벤트", total_events),
    ("지진", earthquake_count),
    ("태풍", typhoon_count),
    ("관련 뉴스", news_count),
]

for col, (label, value) in zip(metric_cols, metrics):
    with col:
        st.markdown(
            f"""
            <div class="metric-card">
              <div class="metric-label">{html.escape(label)}</div>
              <div class="metric-value">{value:,}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# 재난 카드
st.markdown(
    f'<div class="section-title">Disaster Events · {len(filtered_events)} events</div>',
    unsafe_allow_html=True,
)

if sort_criterion == "지진 규모순":
    st.caption("지진은 규모가 큰 순서로, 다른 재난은 최신순으로 표시합니다.")
elif sort_criterion == "태풍 강도순":
    st.caption(
        "태풍은 공식 범주와 확인된 풍속을 기준으로 표시합니다. "
        "그 외 재난은 최신순입니다."
    )
elif sort_criterion in ("사상자순", "재산피해순", "기간순"):
    st.caption(
        "확인된 수치가 있는 사건이 먼저 표시됩니다. "
        "값이 없는 사건은 뒤쪽에 최신순으로 표시합니다."
    )

if not filtered_events:
    st.info(
        "선택한 기간과 재난 종류에 해당하는 이벤트를 찾지 못했습니다. "
        "기간을 늘리거나 다른 재난 종류를 선택해 보세요."
    )
else:
    for i in range(0, len(filtered_events), 2):
        left, right = st.columns(2)

        with left:
            render_event_card(filtered_events[i], i)

        if i + 1 < len(filtered_events):
            with right:
                render_event_card(filtered_events[i + 1], i + 1)

# 뉴스
st.markdown(
    f'<div class="section-title">Related News · {len(filtered_news)} articles</div>',
    unsafe_allow_html=True,
)

if not filtered_news:
    st.info(
        "선택한 기간의 관련 뉴스가 없거나 뉴스 출처에 연결할 수 없습니다."
    )
else:
    for i, article in enumerate(filtered_news[:30]):
        render_news_card(article, i)

# 출처 및 데이터 설명
st.markdown("---")
st.markdown("#### Data Sources")
st.markdown(
    "- [USGS Earthquake Catalog](https://earthquake.usgs.gov/earthquakes/search/)\n"
    "- [GDACS Global Disaster Alert and Coordination System](https://www.gdacs.org/)\n"
    "- [Google News](https://news.google.com/)"
)
st.caption(
    "피해·사상자·기간·태풍 강도 정보는 출처에 따라 제공 여부와 갱신 시점이 다릅니다. "
    "미확인 값은 0으로 간주하지 않으며, 확인되지 않은 수치나 피해 규모를 만들어 내지 않습니다. "
    "지진은 USGS 규모를 사용하고, 태풍은 공개된 공식 범주 또는 단위가 명시된 풍속을 사용합니다. "
    "뉴스는 관련 보도를 찾기 위한 참고 자료이며 공식 피해 집계와 다를 수 있습니다."
)
