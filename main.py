
import re
import html
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# WORLD DISASTER LIVE
# ============================================================

st.set_page_config(
    page_title="WORLD DISASTER LIVE",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

USGS_URL = (
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/"
    "summary/all_day.geojson"
)
GDACS_URL = "https://www.gdacs.org/xml/rss.xml"
GOOGLE_NEWS_URL = "https://news.google.com/rss/search"

CACHE_SECONDS = 300
HTTP_TIMEOUT = 15

HEADERS = {
    "User-Agent": "WorldDisasterLive/1.0",
    "Accept": "application/json, application/xml, text/xml, */*",
}

HAZARDS = {
    "전체": "natural disaster OR earthquake OR flood OR wildfire",
    "태풍": "typhoon OR tropical cyclone OR hurricane",
    "지진": "earthquake",
    "산불": "wildfire OR forest fire",
    "홍수": "flood OR flooding",
    "폭우": "heavy rainfall OR extreme rain OR torrential rain",
    "가뭄": "drought",
    "폭설": "heavy snow OR blizzard OR snowstorm",
    "폭염": "heatwave OR extreme heat",
    "한파": "extreme cold OR cold wave OR freeze",
    "산사태": "landslide OR mudslide",
}

HAZARD_ICONS = {
    "전체": "🌍",
    "태풍": "🌀",
    "지진": "🌎",
    "산불": "🔥",
    "홍수": "🌊",
    "폭우": "🌧️",
    "가뭄": "☀️",
    "폭설": "❄️",
    "폭염": "🌡️",
    "한파": "🥶",
    "산사태": "⛰️",
}


# ============================================================
# 화면 스타일
# ============================================================

st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(
                ellipse at 0% 0%,
                rgba(28, 91, 133, 0.17),
                transparent 45%
            ),
            #080d16;
        color: #eaf0f8;
    }

    [data-testid="stHeader"] {
        background: rgba(8, 13, 22, 0.9);
    }

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 3rem;
        max-width: 1500px;
    }

    .eyebrow {
        color: #60c7ff;
        font-size: 12px;
        letter-spacing: 3px;
        font-weight: 800;
        margin-bottom: 8px;
    }

    .main-title {
        color: #f5f8ff;
        font-size: clamp(28px, 4vw, 45px);
        font-weight: 800;
        line-height: 1.1;
        margin-bottom: 12px;
    }

    .sub-title {
        color: #98a9bf;
        font-size: 14px;
        line-height: 1.8;
    }

    .section-title {
        color: #edf4ff;
        font-size: 19px;
        font-weight: 800;
        margin: 22px 0 12px 0;
    }

    .metric-card {
        background: linear-gradient(
            145deg,
            rgba(25, 39, 57, 0.95),
            rgba(13, 22, 35, 0.95)
        );
        border: 1px solid #26384c;
        border-radius: 14px;
        padding: 18px 20px;
        min-height: 112px;
    }

    .metric-label {
        color: #9dafc5;
        font-size: 12px;
        margin-bottom: 10px;
    }

    .metric-value {
        color: #f4f8ff;
        font-size: 29px;
        font-weight: 800;
    }

    .metric-note {
        color: #7890aa;
        font-size: 11px;
        margin-top: 7px;
    }

    .event-card {
        background: rgba(17, 28, 43, 0.96);
        border: 1px solid #293d53;
        border-radius: 13px;
        padding: 17px;
        margin-bottom: 5px;
    }

    .event-title {
        color: #f1f6ff;
        font-size: 16px;
        font-weight: 700;
        line-height: 1.6;
        margin-bottom: 8px;
    }

    .event-meta {
        color: #8ea5bd;
        font-size: 12px;
        line-height: 1.8;
    }

    .event-desc {
        color: #c2cede;
        font-size: 13px;
        line-height: 1.8;
        margin-top: 10px;
        overflow-wrap: anywhere;
    }

    .source-tag {
        display: inline-block;
        color: #81d4ff;
        background: rgba(47, 142, 192, 0.13);
        border: 1px solid #28546e;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 11px;
        margin-bottom: 9px;
    }

    .detail-box {
        background: #101c2b;
        border: 1px solid #293d53;
        border-radius: 10px;
        padding: 13px;
        margin-bottom: 8px;
        overflow-wrap: anywhere;
    }

    .detail-label {
        color: #8ca6c0;
        font-size: 12px;
        margin-bottom: 4px;
    }

    .detail-value {
        color: #f1f6ff;
        font-size: 15px;
        font-weight: 600;
        overflow-wrap: anywhere;
    }

    .notice {
        border: 1px solid #55472a;
        background: rgba(119, 91, 27, 0.14);
        color: #e8d6a4;
        border-radius: 10px;
        padding: 12px 14px;
        font-size: 12px;
        line-height: 1.8;
    }

    .footer {
        border-top: 1px solid #263446;
        margin-top: 35px;
        padding-top: 17px;
        color: #74879d;
        font-size: 11px;
        line-height: 1.9;
    }

    div[data-testid="stButton"] button {
        border-radius: 9px;
        font-weight: 600;
    }

    a {
        color: #70caff !important;
    }

    [data-testid="stDialog"] > div {
        background: #0b1420;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# UTC 시계 및 마우스 오버 재난 메뉴
# ============================================================

def render_utc_header(selected_hazard):
    """
    시계와 메뉴를 같은 hover 영역 안에 배치합니다.
    iframe 높이를 충분히 확보해 메뉴가 잘리는 문제를 줄입니다.
    """

    menu_items = ""

    for name in HAZARDS:
        url = "?hazard=" + quote(name, safe="")
        active = " active" if name == selected_hazard else ""

        menu_items += f"""
        <a class="hazard-option{active}"
           href="{html.escape(url, quote=True)}"
           target="_top">
            {HAZARD_ICONS.get(name, "🌍")}
            {html.escape(name)}
        </a>
        """

    header_html = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
    <meta charset="utf-8">
    <style>
        * {{
            box-sizing: border-box;
        }}

        html, body {{
            margin: 0;
            padding: 0 3px 12px;
            width: 100%;
            background: transparent;
            color: #f4f8ff;
            font-family: Arial, sans-serif;
            overflow: visible;
        }}

        .topbar {{
            position: relative;
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
            align-items: center;
            width: 100%;
            min-height: 120px;
            padding: 15px 22px;
            border: 1px solid #263c52;
            border-radius: 14px;
            background: linear-gradient(100deg, #101c2b, #0c1421);
        }}

        .clock-area {{
            position: relative;
            grid-column: 2;
            justify-self: center;
            text-align: center;
            padding: 6px 12px;
            border-radius: 10px;
        }}

        .clock-label {{
            color: #80cfff;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 3px;
            margin-bottom: 8px;
        }}

        #clock {{
            color: #f4f8ff;
            font-size: clamp(38px, 5vw, 58px);
            font-weight: 800;
            letter-spacing: 2px;
            font-variant-numeric: tabular-nums;
            white-space: nowrap;
        }}

        .utc {{
            color: #8ca6c0;
            font-size: 12px;
            margin-left: 7px;
            white-space: nowrap;
        }}

        .date-area {{
            grid-column: 3;
            justify-self: end;
            text-align: right;
        }}

        .date-label {{
            color: #8297ad;
            font-size: 11px;
            letter-spacing: 2px;
            margin-bottom: 8px;
        }}

        #date {{
            color: #f4f8ff;
            font-size: 16px;
            font-weight: 700;
            white-space: nowrap;
        }}

        .hover-menu {{
            display: none;
            position: absolute;
            z-index: 999999;
            top: 100%;
            left: 50%;
            transform: translateX(-50%);
            width: 230px;
            max-height: 320px;
            overflow-y: auto;
            padding: 9px;
            background: #101d2c;
            border: 1px solid #38536d;
            border-radius: 12px;
            box-shadow: 0 14px 35px rgba(0, 0, 0, 0.55);
            text-align: left;
        }}

        /*
          메뉴를 시계 영역의 자식으로 두고 top:100%로 붙입니다.
          시계에서 메뉴로 커서를 이동할 때 hover가 끊기지 않습니다.
        */
        .clock-area:hover .hover-menu,
        .clock-area:focus-within .hover-menu {{
            display: block;
        }}

        .menu-heading {{
            padding: 8px 10px;
            color: #8ca6c0;
            font-size: 11px;
            font-weight: 700;
        }}

        .hazard-option {{
            display: block;
            padding: 10px 12px;
            border-radius: 7px;
            color: #dbe8f6 !important;
            text-decoration: none !important;
            font-size: 13px;
            cursor: pointer;
        }}

        .hazard-option:hover,
        .hazard-option.active {{
            background: #193b55;
            color: #8bd6ff !important;
        }}

        @media (max-width: 600px) {{
            .topbar {{
                grid-template-columns: minmax(0, 1fr) auto;
                padding: 12px 8px;
                gap: 4px;
            }}

            .clock-area {{
                grid-column: 1;
                justify-self: start;
                padding: 4px;
            }}

            .clock-label {{
                font-size: 9px;
                letter-spacing: 1px;
            }}

            #clock {{
                font-size: clamp(26px, 7vw, 38px);
                letter-spacing: 0;
            }}

            .utc {{
                font-size: 10px;
                margin-left: 3px;
            }}

            .date-area {{
                grid-column: 2;
            }}

            .date-label {{
                font-size: 9px;
            }}

            #date {{
                font-size: 11px;
            }}

            .hover-menu {{
                left: 0;
                transform: none;
            }}
        }}
    </style>
    </head>

    <body>
        <div class="topbar">
            <div class="clock-area" tabindex="0">
                <div class="clock-label">GLOBAL DISASTER WATCH</div>

                <div>
                    <span id="clock">00:00:00</span>
                    <span class="utc">UTC 기준</span>
                </div>

                <div class="hover-menu">
                    <div class="menu-heading">재난 유형 선택</div>
                    {menu_items}
                </div>
            </div>

            <div class="date-area">
                <div class="date-label">UTC DATE</div>
                <div id="date">0000-00-00</div>
            </div>
        </div>

        <script>
            function updateUTC() {{
                const now = new Date();

                document.getElementById("clock").textContent =
                    String(now.getUTCHours()).padStart(2, "0") + ":" +
                    String(now.getUTCMinutes()).padStart(2, "0") + ":" +
                    String(now.getUTCSeconds()).padStart(2, "0");

                document.getElementById("date").textContent =
                    now.getUTCFullYear() + "-" +
                    String(now.getUTCMonth() + 1).padStart(2, "0") + "-" +
                    String(now.getUTCDate()).padStart(2, "0");
            }}

            updateUTC();
            setInterval(updateUTC, 1000);
        </script>
    </body>
    </html>
    """

    components.html(
        header_html,
        height=430,
        scrolling=False,
    )


# ============================================================
# 공통 자료 요청 함수
# ============================================================

def fetch_json(url, params=None):
    try:
        response = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        LOGGER.warning("JSON 요청 실패: %s", exc)
        return None


def fetch_xml(url, params=None):
    try:
        response = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        return ET.fromstring(response.content)
    except (
        requests.RequestException,
        ET.ParseError,
        ValueError,
    ) as exc:
        LOGGER.warning("XML 요청 실패: %s", exc)
        return None


def clean_text(value):
    if not value:
        return ""

    value = re.sub(r"<[^>]+>", " ", str(value))
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def parse_utc(value):
    if value is None:
        return "시각 정보 없음"

    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(
                value / 1000,
                tz=timezone.utc,
            )
        else:
            dt = datetime.fromisoformat(
                str(value).strip().replace("Z", "+00:00")
            )
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(timezone.utc)

        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    except (ValueError, TypeError, OverflowError, OSError):
        return "시각 정보 없음"


def parse_rss_date(value):
    if not value:
        return None

    try:
        dt = parsedate_to_datetime(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def extract_coordinates_from_xml(item):
    """GDACS XML에 좌표가 존재할 경우 추출합니다."""

    for node in item.iter():
        tag = node.tag.lower()

        if not (
            tag.endswith("point")
            or tag.endswith("pos")
        ):
            continue

        value = clean_text(node.text)

        if not value:
            continue

        numbers = re.findall(
            r"-?\d+(?:\.\d+)?",
            value,
        )

        if len(numbers) < 2:
            continue

        try:
            lat = float(numbers[0])
            lon = float(numbers[1])

            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
        except (ValueError, TypeError):
            pass

    return None, None


# ============================================================
# 피해 수치 자동 탐지
# ============================================================

def extract_impact_numbers(text_value):
    """
    뉴스 제목 및 요약에서 참고용 숫자를 추출합니다.
    이 값은 공식 확정 통계로 취급하지 않습니다.
    """

    text_value = clean_text(text_value)

    result = {
        "사망자": None,
        "부상자": None,
        "이재민": None,
        "피해액": None,
    }

    patterns = {
        "사망자": (
            r"\b(\d[\d,]*)\s+"
            r"(?:people\s+)?(?:killed|dead|deaths|fatalities)\b"
        ),
        "부상자": (
            r"\b(\d[\d,]*)\s+"
            r"(?:people\s+)?(?:injured|wounded)\b"
        ),
        "이재민": (
            r"\b(\d[\d,]*)\s+"
            r"(?:people\s+)?(?:displaced|evacuated|homeless)\b"
        ),
    }

    for label, pattern in patterns.items():
        match = re.search(pattern, text_value, re.I)

        if match:
            try:
                result[label] = int(
                    match.group(1).replace(",", "")
                )
            except (ValueError, TypeError):
                pass

    money_match = re.search(
        r"(?:\$|USD\s*)"
        r"([\d,.]+\s*(?:billion|million|trillion|bn|mn)?)",
        text_value,
        re.I,
    )

    if money_match:
        result["피해액"] = money_match.group(0)

    return result


# ============================================================
# USGS 지진 데이터
# ============================================================

@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def load_earthquakes():
    data = fetch_json(USGS_URL)

    if not isinstance(data, dict):
        return []

    events = []

    for feature in data.get("features", []):
        try:
            properties = feature.get("properties") or {}
            geometry = feature.get("geometry") or {}
            coordinates = geometry.get("coordinates") or []

            magnitude = properties.get("mag")
            place = properties.get("place") or "위치 정보 없음"
            event_time = properties.get("time")

            longitude = (
                float(coordinates[0])
                if len(coordinates) > 0
                else None
            )
            latitude = (
                float(coordinates[1])
                if len(coordinates) > 1
                else None
            )
            depth = (
                float(coordinates[2])
                if len(coordinates) > 2
                else None
            )

            felt = properties.get("felt")

            details = []

            if magnitude is not None:
                details.append(f"규모 {float(magnitude):.1f}")

            details.append(f"위치: {place}")
            details.append(f"발생: {parse_utc(event_time)}")

            if depth is not None:
                details.append(f"깊이: {depth:g} km")

            if felt is not None:
                details.append(f"진동 신고: {felt:,}건")

            events.append({
                "id": str(
                    feature.get("id")
                    or properties.get("code")
                    or ""
                ),
                "kind": "지진",
                "title": f"지진 — {place}",
                "time_raw": event_time or 0,
                "time": parse_utc(event_time),
                "location": place,
                "description": " · ".join(details),
                "source": "USGS",
                "source_url": properties.get("url") or
                    "https://earthquake.usgs.gov/earthquakes/map/",
                "url": properties.get("url") or
                    "https://earthquake.usgs.gov/earthquakes/map/",
                "magnitude": magnitude,
                "felt": felt,
                "depth": depth,
                "latitude": latitude,
                "longitude": longitude,
                "alert_level": None,
                "impact": {
                    "사망자": None,
                    "부상자": None,
                    "이재민": None,
                    "피해액": None,
                },
                "impact_source": "USGS 지진 피드",
                "impact_verified": False,
                "is_news": False,
            })

        except (
            TypeError,
            ValueError,
            IndexError,
            OverflowError,
            OSError,
        ) as exc:
            LOGGER.warning("지진 데이터 변환 실패: %s", exc)

    events.sort(
        key=lambda event: event.get("time_raw") or 0,
        reverse=True,
    )

    return events


# ============================================================
# GDACS 재난 데이터
# ============================================================

def classify_gdacs(title, description, category=""):
    text_value = f"{title} {description} {category}".lower()

    rules = [
        ("태풍", [
            "cyclone", "typhoon", "hurricane", "tropical storm"
        ]),
        ("지진", ["earthquake", "seismic"]),
        ("산불", ["forest fire", "wildfire"]),
        ("홍수", ["flood", "flooding"]),
        ("산사태", ["landslide", "mudslide"]),
        ("폭설", ["snowstorm", "blizzard", "heavy snow"]),
        ("폭우", ["heavy rain", "rainfall", "extreme rain"]),
        ("가뭄", ["drought"]),
        ("폭염", ["heatwave", "heat wave", "extreme heat"]),
        ("한파", ["cold wave", "extreme cold", "cold spell"]),
    ]

    for kind, keywords in rules:
        if any(keyword in text_value for keyword in keywords):
            return kind

    return "기타"


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def load_gdacs_events():
    root = fetch_xml(GDACS_URL)

    if root is None:
        return []

    events = []

    for item in root.findall(".//item"):
        try:
            title = clean_text(item.findtext("title", "제목 없음"))
            description = clean_text(item.findtext("description", ""))
            link = clean_text(item.findtext("link", ""))
            pub_date = clean_text(item.findtext("pubDate", ""))

            category = ""

            for child in item:
                if child.tag.lower().endswith("category"):
                    category = clean_text(child.text or "")
                    break

            kind = classify_gdacs(title, description, category)

            alert_level = None

            for node in item.iter():
                tag = node.tag.lower()

                if "alertlevel" in tag or "alert_level" in tag:
                    candidate = clean_text(node.text)
                    if candidate:
                        alert_level = candidate
                        break

            if not alert_level:
                combined = f"{title} {description}"

                if re.search(r"\bRed alert\b", combined, re.I):
                    alert_level = "적색 경보 (텍스트 탐지)"
                elif re.search(r"\bOrange alert\b", combined, re.I):
                    alert_level = "주황색 경보 (텍스트 탐지)"
                elif re.search(r"\bGreen alert\b", combined, re.I):
                    alert_level = "녹색 경보 (텍스트 탐지)"

            latitude, longitude = extract_coordinates_from_xml(item)
            parsed_date = parse_rss_date(pub_date)

            events.append({
                "id": link or title,
                "kind": kind,
                "title": title,
                "time_raw": pub_date,
                "time": (
                    parsed_date.strftime("%Y-%m-%d %H:%M:%S UTC")
                    if parsed_date
                    else pub_date or "시각 정보 없음"
                ),
                "location": "국제 재난 경보",
                "description": description,
                "source": "GDACS",
                "source_url": "https://www.gdacs.org/",
                "url": link or "https://www.gdacs.org/",
                "latitude": latitude,
                "longitude": longitude,
                "magnitude": None,
                "depth": None,
                "felt": None,
                "alert_level": alert_level,
                "impact": {
                    "사망자": None,
                    "부상자": None,
                    "이재민": None,
                    "피해액": None,
                },
                "impact_source": "GDACS RSS",
                "impact_verified": False,
                "is_news": False,
            })

        except (AttributeError, TypeError, ValueError) as exc:
            LOGGER.warning("GDACS 항목 변환 실패: %s", exc)

    return events


# ============================================================
# Google 뉴스 RSS
# ============================================================

@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def load_news(hazard):
    search_term = HAZARDS.get(hazard, HAZARDS["전체"])

    params = {
        "q": search_term,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }

    root = fetch_xml(GOOGLE_NEWS_URL, params=params)

    if root is None:
        return []

    events = []

    for item in root.findall(".//item"):
        try:
            title = clean_text(item.findtext("title", "제목 없음"))
            link = clean_text(item.findtext("link", ""))
            pub_date = clean_text(item.findtext("pubDate", ""))
            description = clean_text(item.findtext("description", ""))

            source_name = "Google 뉴스 RSS"
            source_node = item.find("source")

            if source_node is not None and source_node.text:
                source_name = clean_text(source_node.text)

            parsed_date = parse_rss_date(pub_date)

            impact = extract_impact_numbers(
                f"{title}. {description}"
            )

            events.append({
                "id": link or title,
                "kind": hazard,
                "title": title,
                "time_raw": pub_date,
                "time": (
                    parsed_date.strftime("%Y-%m-%d %H:%M:%S UTC")
                    if parsed_date
                    else pub_date or "발행 시각 정보 없음"
                ),
                "location": "기사에서 확인",
                "description": description or
                    "기사 요약이 제공되지 않았습니다.",
                "source": source_name,
                "source_url": link or "https://news.google.com/",
                "url": link,
                "latitude": None,
                "longitude": None,
                "magnitude": None,
                "depth": None,
                "felt": None,
                "alert_level": None,
                "impact": impact,
                "impact_source": "뉴스 제목 및 요약 자동 탐지",
                "impact_verified": False,
                "is_news": True,
            })

        except (AttributeError, TypeError, ValueError) as exc:
            LOGGER.warning("뉴스 항목 변환 실패: %s", exc)

    return events


# ============================================================
# 표시 보조 함수
# ============================================================

def safe(value):
    return html.escape(str(value or ""))


def format_number(value):
    if value is None:
        return "미확인"

    try:
        return f"{int(value):,}"
    except (ValueError, TypeError, OverflowError):
        return str(value)


def has_coordinates(event):
    lat = event.get("latitude")
    lon = event.get("longitude")

    if lat is None or lon is None:
        return False

    try:
        return (
            -90 <= float(lat) <= 90
            and -180 <= float(lon) <= 180
        )
    except (ValueError, TypeError):
        return False


# ============================================================
# 재난 카드
# ============================================================

def render_event_card(event, section, index):
    title = safe(event.get("title", "제목 없음"))
    source = safe(event.get("source", "출처 정보 없음"))
    description = safe(event.get("description", ""))
    event_time = safe(event.get("time", "시각 정보 없음"))

    st.markdown(
        f"""
        <div class="event-card">
            <div class="source-tag">{source}</div>
            <div class="event-title">{title}</div>
            <div class="event-meta">🕒 {event_time}</div>
            <div class="event-desc">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "＋ 상세 정보 보기",
        key=f"detail_{section}_{index}",
        use_container_width=True,
    ):
        st.session_state["selected_disaster"] = event
        st.session_state["show_disaster_dialog"] = True
        st.rerun()


# ============================================================
# 중앙 상세 정보 모달
# ============================================================

@st.dialog("🌍 재난 상세 정보", width="large")
def show_disaster_dialog(event, related_articles):
    kind = event.get("kind") or "재난"
    title = event.get("title") or "제목 없음"
    source = event.get("source") or "출처 정보 없음"
    source_url = event.get("source_url") or ""
    event_url = event.get("url") or ""
    description = event.get("description") or ""
    event_time = event.get("time") or "시각 정보 없음"

    st.markdown(f"### {HAZARD_ICONS.get(kind, '🌍')} {kind}")
    st.markdown(f"## {title}")

    st.caption(
        "자료에 기록된 시각은 실제 재난 발생 시각과 "
        "다를 수 있습니다."
    )

    # 기본 정보
    st.markdown("### 📌 기본 정보")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            f"""
            <div class="detail-box">
                <div class="detail-label">재난 유형</div>
                <div class="detail-value">{safe(kind)}</div>
                <div class="detail-label" style="margin-top:12px">
                    자료 제공처
                </div>
                <div class="detail-value">{safe(source)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="detail-box">
                <div class="detail-label">자료에 기록된 시각</div>
                <div class="detail-value">{safe(event_time)}</div>
                <div class="detail-label" style="margin-top:12px">
                    위치
                </div>
                <div class="detail-value">
                    {safe(event.get("location", "미확인"))}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if kind == "지진":
        st.markdown("#### 지진 정보")

        quake_cols = st.columns(3)

        magnitude = event.get("magnitude")
        depth = event.get("depth")
        felt = event.get("felt")

        values = [
            (
                "규모",
                f"{float(magnitude):.1f}"
                if magnitude is not None
                else "미확인",
            ),
            (
                "진앙 깊이",
                f"{float(depth):g} km"
                if depth is not None
                else "미확인",
            ),
            (
                "진동 신고",
                format_number(felt)
                if felt is not None
                else "미확인",
            ),
        ]

        for col, (label, value) in zip(quake_cols, values):
            with col:
                st.metric(label, value)

    if event.get("alert_level"):
        st.info(f"경보 등급: {event['alert_level']}")

    if description:
        st.markdown("#### 사건 설명")
        st.write(description)

    # 지도와 좌표
    st.markdown("### 🗺️ 위치 지도 및 좌표")

    if has_coordinates(event):
        lat = float(event["latitude"])
        lon = float(event["longitude"])

        coord_col1, coord_col2 = st.columns(2)

        with coord_col1:
            st.metric("위도", f"{lat:.5f}°")

        with coord_col2:
            st.metric("경도", f"{lon:.5f}°")

        map_data = pd.DataFrame({
            "latitude": [lat],
            "longitude": [lon],
        })

        st.map(
            map_data,
            latitude="latitude",
            longitude="longitude",
            zoom=5,
            use_container_width=True,
        )

        map_url = (
            "https://www.openstreetmap.org/"
            f"?mlat={lat}&mlon={lon}"
            f"#map=6/{lat}/{lon}"
        )

        st.markdown(f"[지도에서 크게 보기 ↗]({map_url})")

        st.caption(
            "좌표는 제공처가 제공한 값입니다. "
            "정확한 피해 지점과 일치하지 않을 수도 있습니다."
        )
    else:
        st.info(
            "이 항목에는 지도에 표시할 좌표가 없습니다. "
            "원문 자료에서 위치를 확인해 주세요."
        )

    # 피해 현황
    st.markdown("### 🚨 피해 현황")

    impact = event.get("impact") or {}
    impact_cols = st.columns(4)

    for col, label in zip(
        impact_cols,
        ["사망자", "부상자", "이재민", "피해액"],
    ):
        value = impact.get(label)

        if value is None:
            display_value = "미확인"
        elif isinstance(value, (int, float)):
            display_value = format_number(value)
        else:
            display_value = str(value)

        with col:
            st.metric(label, display_value)

    st.caption(
        "피해 수치 출처: "
        + str(event.get("impact_source", "출처 정보 없음"))
    )

    if event.get("impact_verified"):
        st.success("공식 자료에서 확인된 피해 수치입니다.")
    elif event.get("is_news"):
        st.warning(
            "뉴스 제목·요약에서 자동 탐지한 참고 수치입니다. "
            "공식 확정 통계로 검증되지 않았으므로 "
            "원문 기사를 확인해야 합니다."
        )
    else:
        st.info(
            "연결된 자료에서 공식 피해 수치를 확인하지 못했습니다. "
            "미확인은 피해가 없다는 뜻이 아닙니다."
        )

    # 관련 기사
    st.markdown("### 📰 관련 기사 및 원문")

    if event_url.startswith(("https://", "http://")):
        st.markdown(f"[현재 항목 원문 보기 ↗]({event_url})")

    displayed = 0

    for article in related_articles or []:
        article_url = article.get("url", "")

        if article_url and article_url == event_url:
            continue

        article_title = article.get("title") or "제목 없음"
        article_source = article.get("source") or "출처 미확인"
        article_time = article.get("time") or "시각 미확인"

        with st.container(border=True):
            st.markdown(f"**{article_title}**")
            st.caption(f"{article_source} · {article_time}")

            if article_url.startswith(("https://", "http://")):
                st.markdown(f"[기사 원문 열기 ↗]({article_url})")

        displayed += 1

        if displayed >= 5:
            break

    if displayed == 0 and not event_url:
        st.write("현재 표시할 기사 링크가 없습니다.")

    # 출처와 갱신 정보
    st.markdown("### 🔎 출처 및 갱신 정보")

    st.markdown(
        f"""
        <div class="detail-box">
            <div class="detail-label">자료 제공처</div>
            <div class="detail-value">{safe(source)}</div>
            <div class="detail-label" style="margin-top:12px">
                데이터에 기록된 시각
            </div>
            <div class="detail-value">{safe(event_time)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if source_url.startswith(("https://", "http://")):
        st.markdown(f"[제공처 사이트 ↗]({source_url})")

    st.caption(
        "팝업 표시 시각(UTC): "
        + datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    )

    st.caption(
        f"앱 캐시 기준 최대 {CACHE_SECONDS // 60}분. "
        "팝업 표시 시각은 제공처의 실제 데이터 갱신 시각과 다를 수 있습니다."
    )

    if st.button(
        "닫기",
        key="close_disaster_dialog",
        use_container_width=True,
    ):
        st.session_state["show_disaster_dialog"] = False
        st.session_state["selected_disaster"] = None
        st.rerun()


# ============================================================
# 선택한 재난 유형 읽기
# ============================================================

try:
    selected_hazard = st.query_params.get("hazard", "전체")
except Exception:
    selected_hazard = "전체"

if isinstance(selected_hazard, list):
    selected_hazard = selected_hazard[0] if selected_hazard else "전체"

if selected_hazard not in HAZARDS:
    selected_hazard = "전체"


# ============================================================
# 헤더
# ============================================================

render_utc_header(selected_hazard)

st.markdown(
    """
    <div style="margin-top:20px">
        <div class="eyebrow">LIVE GLOBAL MONITORING</div>
        <div class="main-title">WORLD DISASTER LIVE</div>
        <div class="sub-title">
            전 세계 자연재해 경보와 최신 보도를 한곳에서 확인합니다.<br>
            시계는 UTC 기준이며 초 단위로 갱신됩니다.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 데이터 수집
# ============================================================

with st.spinner("세계 재난 정보를 수집하고 있습니다..."):
    earthquake_events = load_earthquakes()
    gdacs_events = load_gdacs_events()
    news_events = load_news(selected_hazard)

if selected_hazard == "전체":
    primary_events = gdacs_events + earthquake_events
else:
    primary_events = [
        event
        for event in gdacs_events
        if event.get("kind") == selected_hazard
    ]

    if selected_hazard == "지진":
        primary_events += earthquake_events

# 같은 링크가 중복으로 표시되지 않게 정리
unique_events = []
seen = set()

for event in primary_events:
    key = event.get("url") or event.get("title")

    if key and key not in seen:
        seen.add(key)
        unique_events.append(event)

primary_events = unique_events


# ============================================================
# 요약 지표
# ============================================================

metric_cols = st.columns(4)

metrics = [
    (
        "선택 유형 경보",
        f"{len(primary_events):,}",
        "전체 재난 경보" if selected_hazard == "전체"
        else f"{selected_hazard} 관련 경보",
    ),
    (
        "최근 지진",
        f"{len(earthquake_events):,}",
        "USGS 최근 24시간",
    ),
    (
        "관련 기사",
        f"{len(news_events):,}",
        "Google 뉴스 RSS 검색 결과",
    ),
    (
        "자료 캐시",
        "5분",
        "수동 갱신 가능",
    ),
]

for col, (label, value, note) in zip(metric_cols, metrics):
    with col:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">{safe(label)}</div>
                <div class="metric-value">{safe(value)}</div>
                <div class="metric-note">{safe(note)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# 수동 새로고침
# ============================================================

st.write("")

left, right = st.columns([3, 1])

with left:
    st.caption(
        "공개 데이터 제공처에 연결합니다. "
        "연결 상태와 제공처 갱신 주기에 따라 결과가 달라질 수 있습니다."
    )

with right:
    if st.button(
        "↻ 최신 자료 다시 불러오기",
        use_container_width=True,
    ):
        load_earthquakes.clear()
        load_gdacs_events.clear()
        load_news.clear()
        st.rerun()


# ============================================================
# 재난 경보 목록
# ============================================================

st.markdown(
    '<div class="section-title">📡 재난 경보 및 발생 현황</div>',
    unsafe_allow_html=True,
)

if primary_events:
    for index, event in enumerate(primary_events[:30]):
        render_event_card(event, "alert", index)
else:
    st.info(
        "현재 선택한 유형에서 표시할 경보를 찾지 못했습니다. "
        "데이터 범위나 연결 상태에 따라 결과가 비어 있을 수 있습니다."
    )


# ============================================================
# 최신 기사 목록
# ============================================================

st.markdown(
    '<div class="section-title">📰 최신 관련 기사</div>',
    unsafe_allow_html=True,
)

if news_events:
    st.caption(
        "기사 발행 시각과 실제 재난 발생 시각은 다를 수 있습니다."
    )

    for index, event in enumerate(news_events[:20]):
        render_event_card(event, "news", index)
else:
    st.warning(
        "뉴스 RSS를 불러오지 못했거나 검색 결과가 없습니다. "
        "잠시 후 다시 시도해 주세요."
    )


# ============================================================
# 데이터 출처 안내
# ============================================================

st.markdown(
    """
    <div class="section-title">🔎 데이터 출처</div>

    <div class="event-card">
        <div class="event-title">USGS · 미국 지질조사국</div>
        <div class="event-desc">
            최근 지진의 규모, 위치, 발생 시각, 깊이 및 진동 신고 정보.
        </div>
        <a href="https://earthquake.usgs.gov/earthquakes/feed/"
           target="_blank" rel="noopener noreferrer">
            USGS 실시간 지진 데이터 ↗
        </a>
    </div>

    <div class="event-card">
        <div class="event-title">GDACS · 국제 재난 경보</div>
        <div class="event-desc">
            주요 국제 재난 이벤트와 경보 정보.
        </div>
        <a href="https://www.gdacs.org/"
           target="_blank" rel="noopener noreferrer">
            GDACS 공식 사이트 ↗
        </a>
    </div>

    <div class="event-card">
        <div class="event-title">Google 뉴스 RSS</div>
        <div class="event-desc">
            재난 유형별 뉴스 검색 결과입니다.
            과거 사건이나 중복 보도가 포함될 수 있습니다.
        </div>
        <a href="https://news.google.com/"
           target="_blank" rel="noopener noreferrer">
            Google 뉴스 ↗
        </a>
    </div>

    <div class="notice">
        <b>피해 수치 안내</b><br>
        공식 수치를 확인하지 못하면 미확인으로 표시합니다.
        뉴스에서 자동 탐지한 숫자는 공식 확정 통계가 아닐 수 있습니다.
        실제 긴급 대응은 해당 지역의 공식 재난 당국 안내를 우선하세요.
    </div>

    <div class="footer">
        WORLD DISASTER LIVE · Global natural disaster monitor<br>
        시간 기준: UTC · 시계는 브라우저에서 1초마다 갱신<br>
        데이터 캐시: 300초
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 상세 정보 중앙 모달 실행
# ============================================================

if (
    st.session_state.get("show_disaster_dialog", False)
    and st.session_state.get("selected_disaster")
):
    selected_event = st.session_state["selected_disaster"]

    show_disaster_dialog(
        selected_event,
        news_events,
    )
