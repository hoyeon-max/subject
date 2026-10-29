# main.py
import re
import html
import requests
import streamlit as st
import streamlit.components.v1 as components
import xml.etree.ElementTree as ET

from datetime import datetime, date, timedelta, timezone
from email.utils import parsedate_to_datetime

# =========================================================
# 페이지 설정
# =========================================================
st.set_page_config(
    page_title="WORLD DISASTER LIVE",
    page_icon="🌍",
    layout="wide",
)

BG = "#0f172a"
PANEL = "#172238"
BORDER = "#334155"
TEXT = "#e2e8f0"
MUTED = "#94a3b8"
UTC = timezone.utc

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
GDACS_URL = "https://www.gdacs.org/xml/rss.xml"
NEWS_URL = "https://news.google.com/rss/search"

HAZARDS = [
    "All", "Typhoon", "Earthquake", "Wildfire", "Flood", "Heavy Rain",
    "Drought", "Heavy Snow", "Heatwave", "Cold Wave", "Landslide",
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
    "최신순", "사상자순", "재산피해순", "기간순",
    "지진 규모순", "태풍 강도순",
]

st.markdown(
    f"""
    <style>
    .stApp {{background:{BG}; color:{TEXT};}}
    header[data-testid="stHeader"] {{background:{BG};}}
    .block-container {{padding-top:1rem; max-width:1600px;}}
    .main-title {{
        text-align:center; font-size:2.6rem; font-weight:900;
        letter-spacing:.12rem; color:#f8fafc; margin:.2rem 0;
    }}
    .subtitle {{text-align:center;color:{MUTED};margin-bottom:1rem;}}
    .section-title {{
        font-size:1.15rem;font-weight:800;color:#f8fafc;
        margin:1.2rem 0 .65rem;
    }}
    .event-card,.news-card {{
        background:{PANEL};border:1px solid {BORDER};
        border-radius:14px;padding:1rem;margin-bottom:.8rem;
        min-height:150px;overflow-wrap:anywhere;
    }}
    .event-title {{font-size:1.02rem;font-weight:800;color:#f8fafc;line-height:1.5;}}
    .event-meta {{color:{MUTED};font-size:.86rem;margin-top:.45rem;line-height:1.8;}}
    .metric-card {{
        background:{PANEL};border:1px solid {BORDER};
        border-radius:12px;padding:.8rem;text-align:center;
    }}
    .metric-label {{color:{MUTED};font-size:.85rem;}}
    .metric-value {{color:#f8fafc;font-size:1.35rem;font-weight:800;margin-top:.3rem;}}
    div.stButton>button {{
        border-radius:9px;border:1px solid {BORDER};
        background:{PANEL};color:{TEXT};font-weight:700;min-height:2.5rem;
    }}
    div.stButton>button:hover {{border-color:#38bdf8;color:#7dd3fc;}}
    a {{color:#7dd3fc !important;}}
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# 공통 유틸리티
# =========================================================
def now_utc():
    return datetime.now(UTC)


def to_utc(value):
    if not value:
        return None
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            value = str(value).strip()
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            dt = datetime.fromisoformat(value)
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
        return to_utc(value)


def fmt_time(value):
    dt = to_utc(value)
    return dt.strftime("%Y-%m-%d %H:%M UTC") if dt else "시간 미확인"


def safe_text(value):
    if value is None:
        return ""
    return html.unescape(re.sub(r"<[^>]*>", " ", str(value))).strip()


def number_from_text(value):
    if value is None:
        return None
    try:
        match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
        return float(match.group(0)) if match else None
    except (ValueError, TypeError):
        return None


def get_tag(element, names):
    wanted = {x.lower() for x in names}
    for child in element.iter():
        name = child.tag.split("}")[-1].lower()
        if name in wanted and child.text and child.text.strip():
            return child.text.strip()
    return ""


def is_in_period(value, start_dt, end_dt):
    dt = to_utc(value)
    return bool(dt and start_dt <= dt < end_dt)


def hazard_ko(hazard):
    return HAZARD_KO.get(hazard, "기타 재난")


# =========================================================
# 피해 정보 추출
# 상태는 확인된 정보만 사용한다.
# confirmed: 확인된 숫자 / ongoing: 집계 중 / unknown: 미확인
# =========================================================
ONGOING_PATTERNS = [
    r"\bbeing counted\b",
    r"\bcounting is ongoing\b",
    r"\bstill counting\b",
    r"\bassessment is ongoing\b",
    r"\bunder assessment\b",
    r"\bbeing assessed\b",
    r"\bdamage assessment is underway\b",
    r"\bcasualty figures? (?:are|is) still being assessed\b",
    r"\bdeath toll (?:is|remains) unclear\b",
    r"\bsearch and rescue operations? (?:are|remain) ongoing\b",
    r"\bthe number of (?:deaths|missing|casualties) remains unclear\b",
    r"\bpreliminary assessment\b",
    r"\bongoing assessment\b",
    r"\b집계 중\b",
    r"\b집계중\b",
    r"\b피해 집계가 진행\b",
    r"\b피해 규모를 파악 중\b",
    r"\b피해를 파악 중\b",
    r"\b수색 작업이 진행\b",
    r"\b인명 피해를 확인 중\b",
]

UNKNOWN_PATTERNS = [
    r"\bunknown\b",
    r"\bnot yet known\b",
    r"\bnot available\b",
    r"\bno information\b",
    r"\bnot reported\b",
    r"\bnot disclosed\b",
    r"\b미확인\b",
    r"\b확인되지 않\b",
    r"\b공개되지 않\b",
]


def has_pattern(text, patterns):
    text = safe_text(text).lower()
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def parse_count(text, patterns):
    """명시적으로 기재된 인원만 추출."""
    text = safe_text(text).lower()

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1).replace(",", ""))
            except (ValueError, IndexError):
                continue
    return None


DEATH_PATTERNS = [
    r"\b(\d[\d,]*)\s+(?:people\s+)?(?:were\s+)?killed\b",
    r"\b(\d[\d,]*)\s+deaths?\b",
    r"\b(\d[\d,]*)\s+fatalities\b",
    r"\bdeath toll\s*(?:of|:|is)?\s*(\d[\d,]*)\b",
    r"\bdeaths?\s*:\s*(\d[\d,]*)\b",
]

MISSING_PATTERNS = [
    r"\b(\d[\d,]*)\s+(?:people\s+)?missing\b",
    r"\b(\d[\d,]*)\s+persons?\s+are\s+missing\b",
    r"\bmissing\s*(?:persons?)?\s*:\s*(\d[\d,]*)\b",
]

INJURED_PATTERNS = [
    r"\b(\d[\d,]*)\s+(?:people\s+)?injured\b",
    r"\b(\d[\d,]*)\s+wounded\b",
    r"\binjured\s*:\s*(\d[\d,]*)\b",
]


def parse_zero_if_explicit(text, kind):
    """
    사망자나 실종자가 없다는 표현이 명시된 경우에만 0으로 처리.
    """
    text = safe_text(text).lower()

    if kind == "deaths":
        patterns = [
            r"\bno deaths\b",
            r"\bno fatalities\b",
            r"\bno one was killed\b",
            r"\bno people were killed\b",
            r"\b사망자 없음\b",
            r"\b사망자는 없\b",
        ]
    elif kind == "missing":
        patterns = [
            r"\bno one is missing\b",
            r"\bno missing persons\b",
            r"\bno people are missing\b",
            r"\b실종자 없음\b",
            r"\b실종자는 없\b",
        ]
    else:
        return None

    return 0 if any(re.search(p, text) for p in patterns) else None


def extract_status(text, value, related_patterns=()):
    """
    확인된 숫자가 있으면 confirmed.
    숫자가 없으면 관련 집계 진행 표현을 확인한 뒤 ongoing/unknown 결정.
    """
    if value is not None:
        return "confirmed"

    text = safe_text(text).lower()

    if has_pattern(text, ONGOING_PATTERNS):
        return "ongoing"

    # 관련 주제의 집계가 진행 중이라는 명시적 표현이 있을 때만 ongoing
    if related_patterns and any(re.search(p, text) for p in related_patterns):
        return "ongoing"

    return "unknown"


def status_label(value, status, suffix="", money=False):
    if status == "ongoing":
        return "집계 중"
    if status != "confirmed" or value is None:
        return "미확인"

    if money:
        return f"${value:,.0f}"
    return f"{int(value):,}{suffix}"


def parse_damage_usd(text):
    """
    피해액이 달러 금액과 단위로 명시된 경우만 추출.
    환율 변환이나 다른 통화의 추정 환산은 하지 않는다.
    """
    text = safe_text(text).lower()

    patterns = [
        r"(?:damage|losses|economic losses|property damage)"
        r"[^.]{0,70}?\$\s*(\d+(?:\.\d+)?)\s*(billion|million|thousand|bn|mn|m|b)?",
        r"\$\s*(\d+(?:\.\d+)?)\s*(billion|million|thousand|bn|mn|m|b)"
        r"[^.]{0,70}?(?:damage|losses|damages)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
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
    text = safe_text(text).lower()
    patterns = [
        r"\b(?:magnitude|mag)\s*(?:of|:|=)?\s*(\d+(?:\.\d+)?)",
        r"\bmw\s*(\d+(?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))
    return None


def parse_wind_kmh(text):
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
    match = re.search(r"\bcategory\s*([1-5])\b", text)
    if match:
        return int(match.group(1))
    match = re.search(r"\bcat\s*([1-5])\b", text)
    return int(match.group(1)) if match else None


def parse_duration_days(text, start_time=None, end_time=None):
    start_dt = to_utc(start_time)
    end_dt = to_utc(end_time)

    if start_dt and end_dt and end_dt >= start_dt:
        return (end_dt - start_dt).total_seconds() / 86400

    text = safe_text(text).lower()

    match = re.search(r"\b(\d+(?:\.\d+)?)\s*days?\b", text)
    if match:
        return float(match.group(1))

    match = re.search(r"\b(\d+(?:\.\d+)?)\s*hours?\b", text)
    if match:
        return float(match.group(1)) / 24

    match = re.search(r"\b(\d+(?:\.\d+)?)\s*weeks?\b", text)
    if match:
        return float(match.group(1)) * 7

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
    if "drought" in text:
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


def make_event(
    event_id, title, hazard, location, event_time,
    description="", source_url="", source="",
    latitude=None, longitude=None, magnitude=None,
    wind_kmh=None, typhoon_category=None,
    start_time=None, end_time=None,
):
    title = safe_text(title) or "제목 미확인"
    description = safe_text(description)
    combined = f"{title}. {description}"

    deaths = parse_count(combined, DEATH_PATTERNS)
    missing = parse_count(combined, MISSING_PATTERNS)
    injured = parse_count(combined, INJURED_PATTERNS)

    if deaths is None:
        deaths = parse_zero_if_explicit(combined, "deaths")
    if missing is None:
        missing = parse_zero_if_explicit(combined, "missing")

    # 개별 항목별로 상태를 판단한다.
    deaths_status = extract_status(
        combined,
        deaths,
        related_patterns=[
            r"\bdeath toll\b", r"\bdeaths?\b", r"\bfatalit(?:y|ies)\b",
            r"\b사망자\b", r"\b사망\b",
        ],
    )
    missing_status = extract_status(
        combined,
        missing,
        related_patterns=[
            r"\bmissing\b", r"\bmissing persons?\b",
            r"\b실종자\b", r"\b실종\b",
        ],
    )

    damage = parse_damage_usd(combined)
    damage_status = extract_status(
        combined,
        damage,
        related_patterns=[
            r"\bdamage\b", r"\blosses\b", r"\beconomic loss\b",
            r"\b재산 피해\b", r"\b재산피해\b", r"\b피해액\b",
        ],
    )

    magnitude = magnitude if magnitude is not None else parse_magnitude(combined)
    wind_kmh = wind_kmh if wind_kmh is not None else parse_wind_kmh(combined)
    typhoon_category = (
        typhoon_category
        if typhoon_category is not None
        else parse_typhoon_category(combined)
    )

    start_time = to_utc(start_time) or to_utc(event_time)
    end_time = to_utc(end_time)
    duration_days = parse_duration_days(combined, start_time, end_time)

    return {
        "id": str(event_id),
        "title": title,
        "hazard": hazard,
        "location": safe_text(location) or "지역 미확인",
        "time": to_utc(event_time),
        "start_time": start_time,
        "end_time": end_time,
        "description": description,
        "source_url": source_url or "",
        "source": source or "",
        "latitude": number_from_text(latitude),
        "longitude": number_from_text(longitude),
        "deaths": deaths,
        "deaths_status": deaths_status,
        "missing": missing,
        "missing_status": missing_status,
        "injured": injured,
        "damage": damage,
        "damage_status": damage_status,
        "magnitude": magnitude,
        "wind_kmh": wind_kmh,
        "typhoon_category": typhoon_category,
        "duration_days": duration_days,
    }


# =========================================================
# UTC 시계
# =========================================================
def render_utc_header():
    components.html(
        """
        <div style="position:relative;background:#0f172a;color:#f8fafc;
                    padding:4px 0 10px;text-align:center;font-family:Arial,sans-serif">
          <div id="clock" style="font-size:clamp(42px,7vw,76px);font-weight:900;
                               letter-spacing:2px;line-height:1.1">--:--:--</div>
          <div style="color:#94a3b8;font-size:13px;letter-spacing:3px">UTC</div>
          <div id="clockdate" style="position:absolute;right:5px;top:8px;
                                    color:#94a3b8;font-size:12px">----</div>
        </div>
        <script>
          function tick() {
            const now = new Date();
            document.getElementById("clock").textContent =
              new Intl.DateTimeFormat("en-GB", {
                timeZone:"UTC",hour:"2-digit",minute:"2-digit",
                second:"2-digit",hour12:false
              }).format(now);
            document.getElementById("clockdate").textContent =
              new Intl.DateTimeFormat("en-GB", {
                timeZone:"UTC",year:"numeric",month:"short",day:"2-digit"
              }).format(now) + " UTC";
          }
          tick();
          setInterval(tick,1000);
        </script>
        """,
        height=120,
        scrolling=False,
    )


# =========================================================
# 날짜 선택
# =========================================================
def initialize_period():
    today = now_utc().date()
    st.session_state.setdefault("period_start", today - timedelta(days=6))
    st.session_state.setdefault("period_end", today)
    st.session_state.setdefault("period_start_input", st.session_state.period_start)
    st.session_state.setdefault("period_end_input", st.session_state.period_end)


def render_period_selector():
    initialize_period()
    today = now_utc().date()

    st.markdown('<div class="section-title">Date Range (UTC)</div>', unsafe_allow_html=True)

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

    start = st.session_state.period_start
    end = st.session_state.period_end

    if start > end:
        st.error("시작 날짜와 종료 날짜를 확인해 주세요.")
        return None, None

    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=UTC)

    st.caption(f"선택 기간: {start:%Y-%m-%d} 00:00 UTC ~ {end:%Y-%m-%d} 23:59 UTC")
    return start_dt, end_dt


# =========================================================
# USGS 지진
# =========================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_earthquakes(start_iso, end_iso):
    response = requests.get(
        USGS_URL,
        params={
            "format": "geojson",
            "starttime": start_iso,
            "endtime": end_iso,
            "orderby": "time",
            "limit": 1000,
        },
        timeout=25,
        headers={"User-Agent": "WorldDisasterLive/1.0"},
    )
    response.raise_for_status()

    events = []
    for feature in response.json().get("features", []):
        props = feature.get("properties", {}) or {}
        coords = (feature.get("geometry") or {}).get("coordinates") or []

        ts = props.get("time")
        event_time = datetime.fromtimestamp(ts / 1000, tz=UTC) if ts else None
        mag = props.get("mag")
        location = props.get("place") or "지역 미확인"
        title = props.get("title") or f"Earthquake - {location}"

        # USGS는 지진 발생 시각과 규모를 제공하지만,
        # 모든 지진에 사망자·실종자·피해액을 제공하는 것은 아니다.
        event = make_event(
            event_id=feature.get("id") or props.get("code") or title,
            title=title,
            hazard="Earthquake",
            location=location,
            event_time=event_time,
            description=props.get("alert") or "",
            source_url=props.get("url") or "",
            source="USGS",
            latitude=coords[1] if len(coords) > 1 else None,
            longitude=coords[0] if len(coords) > 0 else None,
            magnitude=mag,
        )
        events.append(event)

    return events


# =========================================================
# GDACS RSS
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

        title = get_tag(item, ["title"])
        description = get_tag(item, ["description", "summary"])
        link = get_tag(item, ["link"])
        guid = get_tag(item, ["guid"])
        pub_date = get_tag(item, ["pubDate", "published", "updated"])
        category = get_tag(item, ["category", "eventtype", "eventType"])

        event_time = parse_rss_date(pub_date)
        hazard = identify_hazard(title, description, category)

        location = get_tag(item, ["location", "country", "area"]) or title
        lat = get_tag(item, ["lat", "latitude"])
        lon = get_tag(item, ["lon", "long", "longitude"])

        start_text = get_tag(
            item, ["fromdate", "fromDate", "eventstart", "starttime", "startTime"]
        )
        end_text = get_tag(
            item, ["todate", "toDate", "eventend", "endtime", "endTime"]
        )

        event = make_event(
            event_id=guid or link or f"{title}-{pub_date}",
            title=title,
            hazard=hazard,
            location=location,
            event_time=to_utc(start_text) or event_time,
            description=description,
            source_url=link,
            source="GDACS",
            latitude=lat,
            longitude=lon,
            start_time=to_utc(start_text) or event_time,
            end_time=to_utc(end_text),
        )
        events.append(event)

    unique = {}
    for event in events:
        unique[event["id"]] = event

    return list(unique.values())


# =========================================================
# Google News
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

    query = (
        f"{query_terms.get(hazard, 'natural disaster')} "
        f"after:{start_date.isoformat()} "
        f"before:{(end_date + timedelta(days=1)).isoformat()}"
    )

    response = requests.get(
        NEWS_URL,
        params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
        timeout=25,
        headers={"User-Agent": "WorldDisasterLive/1.0"},
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)

    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
    end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=UTC)

    articles = []
    for item in root.iter():
        if item.tag.split("}")[-1].lower() != "item":
            continue

        title = get_tag(item, ["title"])
        link = get_tag(item, ["link"])
        published = parse_rss_date(get_tag(item, ["pubDate", "published"]))
        source = get_tag(item, ["source"])
        description = get_tag(item, ["description", "summary"])

        if not is_in_period(published, start_dt, end_dt):
            continue

        articles.append({
            "title": safe_text(title),
            "url": link,
            "published": published,
            "source": safe_text(source) or "Google News",
            "description": safe_text(description),
        })

    unique = {}
    for article in articles:
        unique[article["url"] or article["title"]] = article
    return list(unique.values())


# =========================================================
# 정렬
# =========================================================
def sort_known_first(events, key):
    known = [x for x in events if x.get(key) is not None]
    unknown = [x for x in events if x.get(key) is None]

    known.sort(key=lambda x: x[key], reverse=True)
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
        # 사망자 + 부상자 수를 계산할 수 있는 경우에만 정렬한다.
        # 실종자는 별도 항목으로 유지한다.
        for event in events:
            if event.get("deaths") is not None or event.get("injured") is not None:
                event["sort_casualties"] = (event.get("deaths") or 0) + (event.get("injured") or 0)
            else:
                event["sort_casualties"] = None
        return sort_known_first(events, "sort_casualties")

    if criterion == "재산피해순":
        return sort_known_first(events, "damage")

    if criterion == "기간순":
        return sort_known_first(events, "duration_days")

    if criterion == "지진 규모순":
        quakes = [x for x in events if x["hazard"] == "Earthquake"]
        others = [x for x in events if x["hazard"] != "Earthquake"]
        quakes = sort_known_first(quakes, "magnitude")
        others.sort(
            key=lambda x: x.get("time") or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return quakes + others

    if criterion == "태풍 강도순":
        typhoons = [x for x in events if x["hazard"] == "Typhoon"]
        others = [x for x in events if x["hazard"] != "Typhoon"]

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
# 피해 정보 표시
# =========================================================
def display_deaths(event):
    return status_label(
        event.get("deaths"),
        event.get("deaths_status", "unknown"),
        "명",
    )


def display_missing(event):
    return status_label(
        event.get("missing"),
        event.get("missing_status", "unknown"),
        "명",
    )


def display_damage(event):
    return status_label(
        event.get("damage"),
        event.get("damage_status", "unknown"),
        money=True,
    )


def display_duration(event):
    value = event.get("duration_days")
    if value is None:
        return "미확인"
    if value < 1:
        return f"{value * 24:.1f}시간"
    return f"{value:.1f}일"


def display_magnitude(event):
    value = event.get("magnitude")
    return f"M{value:g}" if value is not None else "미확인"


def display_typhoon_strength(event):
    category = event.get("typhoon_category")
    wind = event.get("wind_kmh")

    parts = []
    if category is not None:
        parts.append(f"Category {int(category)}")
    if wind is not None:
        parts.append(f"{wind:.0f} km/h")

    return " / ".join(parts) if parts else "미확인"


# =========================================================
# 이벤트 상세 팝업
# =========================================================
def event_detail(event):
    @st.dialog("Disaster Details", width="large")
    def _detail():
        st.markdown(f"### {event['title']}")
        st.caption(
            f"{hazard_ko(event['hazard'])} · {event['location']} · "
            f"{fmt_time(event['time'])}"
        )

        st.markdown("#### 피해 현황")
        a, b, c = st.columns(3)
        with a:
            st.metric("사망자", display_deaths(event))
        with b:
            st.metric("실종자", display_missing(event))
        with c:
            st.metric("재산 피해", display_damage(event))

        d, e = st.columns(2)
        with d:
            st.metric("부상자", f"{event['injured']:,}명" if event.get("injured") is not None else "미확인")
        with e:
            st.metric("지속 기간", display_duration(event))

        if event["hazard"] == "Earthquake":
            st.metric("지진 규모", display_magnitude(event))

        if event["hazard"] == "Typhoon":
            x, y = st.columns(2)
            with x:
                st.metric("태풍 범주", display_typhoon_strength(event))
            with y:
                st.metric(
                    "최대 풍속",
                    f"{event['wind_kmh']:.0f} km/h"
                    if event.get("wind_kmh") is not None
                    else "미확인",
                )

        st.markdown("#### 상세 설명")
        st.write(event.get("description") or "제공된 상세 설명이 없습니다.")

        lat = event.get("latitude")
        lon = event.get("longitude")
        if lat is not None and lon is not None:
            st.markdown("#### 위치")
            st.write(f"위도: {lat} · 경도: {lon}")
            st.link_button(
                "지도에서 위치 보기",
                f"https://www.google.com/maps?q={lat},{lon}",
                use_container_width=True,
            )
        else:
            st.caption("좌표 정보는 미확인입니다.")

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
    hazard = hazard_ko(event["hazard"])

    strength = ""
    if event["hazard"] == "Earthquake":
        strength = f" · {display_magnitude(event)}"
    elif event["hazard"] == "Typhoon":
        strength = f" · {display_typhoon_strength(event)}"

    st.markdown(
        f"""
        <div class="event-card">
          <div class="event-title">{html.escape(event['title'])}</div>
          <div class="event-meta">
            {html.escape(hazard + strength)}<br>
            {html.escape(event['location'])}<br>
            {html.escape(fmt_time(event['time']))}<br>
            사망자: {html.escape(display_deaths(event))}<br>
            실종자: {html.escape(display_missing(event))}<br>
            재산 피해: {html.escape(display_damage(event))}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "View Details",
        key=f"event_detail_{index}_{event['id']}",
        use_container_width=True,
    ):
        event_detail(event)


def render_news_card(article, index):
    st.markdown(
        f"""
        <div class="news-card">
          <div class="event-title">{html.escape(article.get('title') or '제목 미확인')}</div>
          <div class="event-meta">
            {html.escape(article.get('source') or 'Google News')}<br>
            {html.escape(fmt_time(article.get('published')))}
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
# 메인 화면
# =========================================================
render_utc_header()

st.markdown(
    '<div class="main-title">WORLD DISASTER LIVE</div>'
    '<div class="subtitle">Global Disaster Monitoring Dashboard · UTC</div>',
    unsafe_allow_html=True,
)

top1, top2 = st.columns([4, 1])
with top1:
    st.markdown('<div class="section-title">Hazard Categories</div>', unsafe_allow_html=True)
with top2:
    if st.button("Refresh Data", use_container_width=True):
        load_earthquakes.clear()
        load_gdacs_events.clear()
        load_news.clear()
        st.rerun()

if "hazard" not in st.session_state:
    st.session_state.hazard = "All"

for row_hazards in (HAZARDS[:6], HAZARDS[6:]):
    cols = st.columns(len(row_hazards))
    for col, hazard in zip(cols, row_hazards):
        with col:
            label = f"✓ {hazard}" if st.session_state.hazard == hazard else hazard
            if st.button(label, key=f"hazard_{hazard}", use_container_width=True):
                st.session_state.hazard = hazard
                st.rerun()

start_dt, end_dt = render_period_selector()
if start_dt is None or end_dt is None:
    st.stop()

st.markdown('<div class="section-title">Sorting Criteria</div>', unsafe_allow_html=True)
sort_col1, sort_col2 = st.columns([2, 3])

with sort_col1:
    sort_criterion = st.selectbox(
        "재난 카드 정렬 기준",
        SORT_OPTIONS,
        index=0,
    )
with sort_col2:
    st.caption(
        "사망자·실종자·재산 피해는 출처에서 확인된 값만 표시합니다. "
        "집계 진행이 명시된 경우는 '집계 중', 자료가 없거나 확인할 수 없는 경우는 '미확인'입니다."
    )

events = []
news = []
errors = []

start_iso = start_dt.isoformat().replace("+00:00", "Z")
end_iso = end_dt.isoformat().replace("+00:00", "Z")

with st.spinner("재난 데이터를 불러오는 중입니다..."):
    try:
        events.extend(load_earthquakes(start_iso, end_iso))
    except Exception as exc:
        errors.append(f"USGS 지진 데이터: {exc}")

    try:
        events.extend([
            e for e in load_gdacs_events()
            if is_in_period(e.get("time"), start_dt, end_dt)
        ])
    except Exception as exc:
        errors.append(f"GDACS 재난 데이터: {exc}")

    try:
        news = load_news(
            st.session_state.hazard,
            st.session_state.period_start.isoformat(),
            st.session_state.period_end.isoformat(),
        )
    except Exception as exc:
        errors.append(f"Google News: {exc}")

if errors:
    with st.expander("일부 데이터 출처에 연결할 수 없습니다", expanded=False):
        for error in errors:
            st.warning(error)
        st.caption("일시적인 연결 오류일 수 있습니다. Refresh Data를 눌러 다시 시도해 주세요.")

# 중복 제거
deduped = {}
for event in events:
    deduped[event["id"]] = event
events = list(deduped.values())

# 재난 종류 필터
if st.session_state.hazard != "All":
    events = [e for e in events if e["hazard"] == st.session_state.hazard]

# 정렬
events = sort_events(events, sort_criterion)
news.sort(
    key=lambda x: x.get("published") or datetime.min.replace(tzinfo=UTC),
    reverse=True,
)

# 개요
st.markdown('<div class="section-title">Overview</div>', unsafe_allow_html=True)

metrics = [
    ("재난 이벤트", len(events)),
    ("지진", sum(e["hazard"] == "Earthquake" for e in events)),
    ("태풍", sum(e["hazard"] == "Typhoon" for e in events)),
    ("관련 뉴스", len(news)),
]

metric_cols = st.columns(4)
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

# 재난 이벤트
st.markdown(
    f'<div class="section-title">Disaster Events · {len(events)} events</div>',
    unsafe_allow_html=True,
)

if sort_criterion in ("사상자순", "재산피해순", "기간순"):
    st.caption("확인된 수치가 있는 사건을 우선 표시합니다. 미확인 항목은 뒤쪽에 최신순으로 표시합니다.")
elif sort_criterion == "지진 규모순":
    st.caption("지진은 규모가 큰 순서로 표시하며, 다른 재난은 최신순으로 표시합니다.")
elif sort_criterion == "태풍 강도순":
    st.caption("태풍은 확인된 공식 범주와 풍속 기준으로 표시하며, 다른 재난은 최신순으로 표시합니다.")

if not events:
    st.info("선택한 기간과 재난 종류에 해당하는 이벤트가 없습니다.")
else:
    for i in range(0, len(events), 2):
        left, right = st.columns(2)
        with left:
            render_event_card(events[i], i)
        if i + 1 < len(events):
            with right:
                render_event_card(events[i + 1], i + 1)

# 뉴스
st.markdown(
    f'<div class="section-title">Related News · {len(news)} articles</div>',
    unsafe_allow_html=True,
)

if not news:
    st.info("선택한 기간의 관련 뉴스가 없거나 뉴스 출처에 연결할 수 없습니다.")
else:
    for i, article in enumerate(news[:30]):
        render_news_card(article, i)

# 출처 안내
st.markdown("---")
st.markdown("#### Data Sources")
st.markdown(
    "- [USGS Earthquake Catalog](https://earthquake.usgs.gov/earthquakes/search/)\n"
    "- [GDACS Global Disaster Alert and Coordination System](https://www.gdacs.org/)\n"
    "- [Google News](https://news.google.com/)"
)
st.caption(
    "사망자·실종자·재산 피해는 출처에 명시된 값만 사용합니다. "
    "출처에 집계 진행 사실이 명시된 경우에만 '집계 중'으로 표시합니다. "
    "관련 정보가 없거나 확인할 수 없는 경우는 '미확인'으로 표시하며, "
    "정보가 없다는 이유로 0으로 처리하지 않습니다. "
    "뉴스의 수치는 공식 집계와 다를 수 있으므로 상세 출처를 확인해 주세요."
)
