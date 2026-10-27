
# main.py
# ============================================================
# WORLD DISASTER LIVE
# 세계 자연재해 모니터링 및 상세 정보 팝업
#
# 주요 기능
# 1. UTC 시계 중앙 표시: 초 단위 갱신
# 2. 시계 마우스 오버: 재난 유형 선택
# 3. USGS 최근 24시간 지진 자료
# 4. GDACS 국제 재난 경보
# 5. Google 뉴스 RSS
# 6. 재난 카드의 상세 정보 버튼 -> 중앙 모달 팝업
# 7. 발생 시각, 위치, 피해 현황, 기사, 출처, 좌표 및 지도
# 8. 수동 새로고침과 데이터 캐시
#
# 주의:
# - 제공처에서 확인할 수 없는 피해 숫자는 만들지 않습니다.
# - 뉴스에서 자동 추출한 숫자는 공식 확정 통계로 간주하지 않습니다.
# ============================================================

import re
import html
import logging
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from urllib.parse import quote

import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ------------------------------------------------------------
# 1. 기본 설정
# ------------------------------------------------------------

st.set_page_config(
    page_title="WORLD DISASTER LIVE",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

# 공개 데이터 주소
USGS_URL = (
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/"
    "summary/all_day.geojson"
)

GDACS_URL = "https://www.gdacs.org/xml/rss.xml"
GOOGLE_NEWS_URL = "https://news.google.com/rss/search"

# 데이터는 5분 동안 캐시에 저장합니다.
CACHE_SECONDS = 300
HTTP_TIMEOUT = 15

HEADERS = {
    "User-Agent": "WorldDisasterLive/1.0",
    "Accept": (
        "application/json, application/xml, text/xml, "
        "application/rss+xml, */*"
    ),
}

# 재난 메뉴와 검색어
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


# ------------------------------------------------------------
# 2. 화면 디자인
# ------------------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: Inter, Arial, sans-serif;
    }

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
        padding-top: 1.4rem;
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
        margin: 0 0 12px 0;
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
        margin-bottom: 8px;
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

    .status-line {
        color: #93a7be;
        font-size: 12px;
        line-height: 1.8;
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

    .detail-box {
        background: #101c2b;
        border: 1px solid #293d53;
        border-radius: 10px;
        padding: 13px;
        margin-bottom: 8px;
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
        text-decoration: none;
    }

    a:hover {
        text-decoration: underline;
    }

    /* Streamlit 중앙 모달의 배경 */
    [data-testid="stDialog"] > div {
        background: #0b1420;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# 3. 중앙 UTC 시계와 재난 메뉴
# ------------------------------------------------------------

def render_utc_header(selected_hazard):
    """시계는 중앙에, 날짜는 오른쪽에 표시합니다."""

    menu_items = ""

    for name in HAZARDS:
        url = "?hazard=" + quote(name)

        active_style = (
            "background:#193b55;color:#8bd6ff;"
            if name == selected_hazard
            else ""
        )

        menu_items += (
            '<a class="hazard-option" target="_top" '
            f'href="{html.escape(url, quote=True)}" '
            f'style="{active_style}">'
            f'{HAZARD_ICONS[name]}&nbsp;'
            f'{html.escape(name)}'
            '</a>'
        )

    header_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">

    <style>
        * {{ box-sizing: border-box; }}

        body {{
            margin: 0;
            background: transparent;
            color: #f4f8ff;
            font-family: Arial, sans-serif;
        }}

        .topbar {{
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            align-items: center;
            gap: 12px;
            background: linear-gradient(
                100deg, #101c2b, #0c1421
            );
            border: 1px solid #263c52;
            border-radius: 14px;
            padding: 18px 24px;
            min-height: 120px;
            width: 100%;
        }}

        .clock-area {{
            position: relative;
            display: inline-block;
            grid-column: 2;
            text-align: center;
            min-width: 0;
        }}

        .clock-label {{
            color: #80cfff;
            font-size: 12px;
            letter-spacing: 3px;
            font-weight: 800;
            margin-bottom: 10px;
        }}

        #clock {{
            font-size: clamp(38px, 5vw, 58px);
            font-weight: 800;
            letter-spacing: 2px;
            font-variant-numeric: tabular-nums;
            white-space: nowrap;
            color: #f4f8ff;
            text-shadow: 0 0 22px rgba(75, 177, 255, 0.12);
        }}

        .utc {{
            display: inline-block;
            color: #8ca6c0;
            font-size: 12px;
            margin-left: 8px;
            white-space: nowrap;
        }}

        .date-area {{
            grid-column: 3;
            text-align: right;
            justify-self: end;
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
            z-index: 99999;
            top: calc(100% + 8px);
            left: 50%;
            transform: translateX(-50%);
            width: 215px;
            max-height: 340px;
            overflow-y: auto;
            padding: 8px;
            background: #101d2c;
            border: 1px solid #38536d;
            border-radius: 12px;
            box-shadow: 0 12px 35px rgba(0,0,0,.45);
            text-align: left;
        }}

        .clock-area:hover .hover-menu,
        .clock-area:focus-within .hover-menu {{
            display: block;
        }}

        .hover-menu::before {{
            content: "재난 유형 선택";
            display: block;
            color: #8ca6c0;
            font-size: 11px;
            padding: 8px 10px;
        }}

        .hazard-option {{
            display: block;
            padding: 10px;
            border-radius: 7px;
            color: #dbe8f6 !important;
            font-size: 13px;
            text-decoration: none !important;
        }}

        .hazard-option:hover {{
            background: #1a3046;
            color: #8bd6ff !important;
        }}

        @media(max-width: 600px) {{
            .topbar {{
                grid-template-columns: minmax(0, 1fr) auto;
                padding: 14px 10px;
                gap: 6px;
                min-height: 100px;
            }}

            .clock-area {{
                grid-column: 1;
                text-align: left;
            }}

            #clock {{
                font-size: clamp(27px, 7vw, 38px);
                letter-spacing: 0;
            }}

            .utc {{
                font-size: 10px;
                margin-left: 3px;
            }}

            .clock-label {{
                font-size: 9px;
                letter-spacing: 1px;
            }}

            .date-area {{
                grid-column: 2;
                justify-self: end;
            }}

            #date {{ font-size: 11px; }}
            .date-label {{ font-size: 9px; }}

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
                <div class="clock-label">
                    GLOBAL DISASTER WATCH
                </div>

                <div>
                    <span id="clock">00:00:00</span>
                    <span class="utc">UTC 기준</span>
                </div>

                <div class="hover-menu">
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

                const hh = String(now.getUTCHours()).padStart(2, '0');
                const mm = String(now.getUTCMinutes()).padStart(2, '0');
                const ss = String(now.getUTCSeconds()).padStart(2, '0');

                const yyyy = now.getUTCFullYear();
                const mo = String(now.getUTCMonth() + 1).padStart(2, '0');
                const dd = String(now.getUTCDate()).padStart(2, '0');

                document.getElementById('clock').textContent =
                    hh + ':' + mm + ':' + ss;

                document.getElementById('date').textContent =
                    yyyy + '-' + mo + '-' + dd;
            }}

            updateUTC();
            setInterval(updateUTC, 1000);
        </script>
    </body>
    </html>
    """

    components.html(
        header_html,
        height=145,
        scrolling=False,
    )


# ------------------------------------------------------------
# 4. 공통 자료 요청 함수
# ------------------------------------------------------------

def fetch_json(url, params=None):
    """JSON 자료를 요청합니다. 실패 시 None을 반환합니다."""

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
    """XML 또는 RSS를 요청합니다. 실패 시 None을 반환합니다."""

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
    """HTML 태그와 불필요한 공백을 제거합니다."""

    if not value:
        return ""

    value = re.sub(r"<[^>]+>", " ", str(value))
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def parse_utc(value):
    """시각을 UTC 형식으로 변환합니다."""

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

    except (
        ValueError,
        TypeError,
        OverflowError,
        OSError,
    ):
        return "시각 정보 없음"


def parse_rss_date(value):
    """RSS 날짜를 UTC로 바꿉니다."""

    if not value:
        return None

    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except (TypeError, ValueError, OverflowError):
        return None


def extract_coordinates_from_xml(item):
    """
    GDACS RSS에 좌표가 들어 있으면 위도와 경도를 찾습니다.
    좌표가 없으면 (None, None)을 반환합니다.
    """

    for node in item.iter():
        tag = node.tag.lower()

        if not (
            tag.endswith("point")
            or tag.endswith("pos")
        ):
            continue

        text_value = clean_text(node.text)

        if not text_value:
            continue

        numbers = re.findall(
            r"-?\d+(?:\.\d+)?",
            text_value,
        )

        if len(numbers) < 2:
            continue

        try:
            # GeoRSS point는 일반적으로 위도, 경도 순서입니다.
            lat = float(numbers[0])
            lon = float(numbers[1])

            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon

        except (ValueError, TypeError):
            continue

    return None, None


# ------------------------------------------------------------
# 5. 피해 숫자 탐지
# ------------------------------------------------------------

def extract_impact_numbers(text_value):
    """
    기사 제목과 요약에서 피해 수치를 참고용으로 추출합니다.

    중요:
    이 숫자는 기사 문맥을 완벽하게 이해해 검증한 통계가 아닙니다.
    화면에서는 공식 확정 피해 수치와 구분하여 표시합니다.
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
        match = re.search(
            pattern,
            text_value,
            flags=re.I,
        )

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
        flags=re.I,
    )

    if money_match:
        result["피해액"] = money_match.group(0)

    return result


# ------------------------------------------------------------
# 6. USGS 지진 자료
# ------------------------------------------------------------

@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def load_earthquakes():
    """USGS의 최근 24시간 지진 GeoJSON을 읽습니다."""

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
            else:
                details.append("규모 미집계")

            details.append(f"위치: {place}")
            details.append(f"발생: {parse_utc(event_time)}")

            if depth is not None:
                details.append(f"깊이: {depth:g} km")

            if felt is not None:
                details.append(f"진동 신고: {felt:,}건")

            events.append({
                "id": str(feature.get("id") or properties.get("code") or ""),
                "kind": "지진",
                "title": f"지진 — {place}",
                "time_raw": event_time or 0,
                "time": parse_utc(event_time),
                "event_datetime": (
                    datetime.fromtimestamp(
                        event_time / 1000,
                        tz=timezone.utc,
                    )
                    if event_time
                    else None
                ),
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
                # USGS 피드에는 일반적으로 피해자 통계가 없습니다.
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
            LOGGER.warning("지진 항목 변환 실패: %s", exc)

    events.sort(
        key=lambda event: event.get("time_raw") or 0,
        reverse=True,
    )

    return events


# ------------------------------------------------------------
# 7. GDACS 국제 재난 경보
# ------------------------------------------------------------

def classify_gdacs(title, description, category=""):
    """키워드를 기준으로 GDACS 재난 유형을 분류합니다."""

    text_value = (
        f"{title} {description} {category}"
    ).lower()

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
    """GDACS RSS에서 재난 경보와 가능한 좌표를 가져옵니다."""

    root = fetch_xml(GDACS_URL)

    if root is None:
        return []

    events = []

    for item in root.findall(".//item"):
        try:
            title = clean_text(
                item.findtext("title", "제목 없음")
            )
            description = clean_text(
                item.findtext("description", "")
            )
            link = clean_text(
                item.findtext("link", "")
            )
            pub_date = clean_text(
                item.findtext("pubDate", "")
            )

            category = ""

            for child in item:
                if child.tag.lower().endswith("category"):
                    category = clean_text(child.text or "")
                    break

            kind = classify_gdacs(
                title,
                description,
                category,
            )

            # 경보 등급은 구조화된 필드에서 우선 찾습니다.
            alert_level = None

            for node in item.iter():
                tag = node.tag.lower()

                if "alertlevel" in tag or "alert_level" in tag:
                    candidate = clean_text(node.text)

                    if candidate:
                        alert_level = candidate
                        break

            # RSS 제목/설명에 명시된 등급만 보조적으로 표시합니다.
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
                "event_datetime": parsed_date,
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
                # GDACS RSS 항목에서 직접 확인하지 못한 피해 수치는 미확인.
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


# ------------------------------------------------------------
# 8. Google 뉴스 RSS
# ------------------------------------------------------------

@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def load_news(hazard):
    """선택한 유형에 대한 뉴스 RSS 검색 결과를 가져옵니다."""

    search_term = HAZARDS.get(
        hazard,
        HAZARDS["전체"],
    )

    params = {
        "q": search_term,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }

    root = fetch_xml(
        GOOGLE_NEWS_URL,
        params=params,
    )

    if root is None:
        return []

    events = []

    for item in root.findall(".//item"):
        try:
            title = clean_text(
                item.findtext("title", "제목 없음")
            )
            link = clean_text(
                item.findtext("link", "")
            )
            pub_date = clean_text(
                item.findtext("pubDate", "")
            )
            description = clean_text(
                item.findtext("description", "")
            )

            source_name = "Google 뉴스 RSS"
            source_node = item.find("source")

            if source_node is not None and source_node.text:
                source_name = clean_text(source_node.text)

            parsed_date = parse_rss_date(pub_date)

            # 뉴스 숫자는 참고용 자동 탐지 결과로만 저장합니다.
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
                "event_datetime": parsed_date,
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


# ------------------------------------------------------------
# 9. 공통 화면 표시 도우미
# ------------------------------------------------------------

def safe(value):
    """HTML에 표시할 텍스트를 안전하게 변환합니다."""
    return html.escape(str(value or ""))


def format_number(value):
    """숫자를 천 단위 쉼표로 표시합니다."""

    if value is None:
        return "미확인"

    try:
        return f"{int(value):,}"
    except (ValueError, TypeError, OverflowError):
        return str(value)


def has_coordinates(event):
    """유효한 위도와 경도가 있는지 확인합니다."""

    lat = event.get("latitude")
    lon = event.get("longitude")

    if lat is None or lon is None:
        return False

    try:
        return -90 <= float(lat) <= 90 and -180 <= float(lon) <= 180
    except (ValueError, TypeError):
        return False


def render_event_card(event, section, index):
    """
    재난 카드를 그리고 상세 정보 버튼을 만듭니다.

    버튼을 누르면 이벤트를 세션에 저장하고 중앙 모달을 엽니다.
    """

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

    # 각 항목에 고유한 키를 부여해 버튼 충돌을 방지합니다.
    key_value = f"detail_{section}_{index}"

    if st.button(
        "＋ 상세 정보 보기",
        key=key_value,
        use_container_width=True,
    ):
        st.session_state["selected_disaster"] = event
        st.session_state["show_disaster_dialog"] = True
        st.rerun()


# ------------------------------------------------------------
# 10. 중앙 상세 정보 모달
# ------------------------------------------------------------

@st.dialog("🌍 재난 상세 정보", width="large")
def show_disaster_dialog(event, related_articles):
    """
    Streamlit 중앙 모달입니다.

    기본 정보, 피해 통계, 기사, 출처, 좌표와 지도를 표시합니다.
    """

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
        "발생 시각과 기사 발행 시각은 다를 수 있습니다. "
        "아래 시간은 각 자료의 의미에 따라 해석해야 합니다."
    )

    # --------------------------------------------------------
    # A. 기본 정보
    # --------------------------------------------------------

    st.markdown("### 📌 기본 정보")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            '<div class="detail-box">'
            '<div class="detail-label">재난 유형</div>'
            f'<div class="detail-value">{safe(kind)}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="detail-box">'
            '<div class="detail-label">자료 제공처</div>'
            f'<div class="detail-value">{safe(source)}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            '<div class="detail-box">'
            '<div class="detail-label">자료에 기록된 시각</div>'
            f'<div class="detail-value">{safe(event_time)}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="detail-box">'
            '<div class="detail-label">위치</div>'
            f'<div class="detail-value">'
            f'{safe(event.get("location", "미확인"))}'
            '</div></div>',
            unsafe_allow_html=True,
        )

    # 지진 전용 수치
    if kind == "지진":
        st.markdown("#### 지진 정보")

        quake_cols = st.columns(3)

        magnitude = event.get("magnitude")
        depth = event.get("depth")
        felt = event.get("felt")

        quake_values = [
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

        for col, (label, value) in zip(quake_cols, quake_values):
            with col:
                st.metric(label, value)

    # 경보 등급
    if event.get("alert_level"):
        st.info(
            f"경보 등급: {event['alert_level']}"
        )

    # 사건 설명
    if description:
        st.markdown("#### 사건 설명")
        st.write(description)

    # --------------------------------------------------------
    # B. 지도와 좌표
    # --------------------------------------------------------

    st.markdown("### 🗺️ 위치 지도 및 좌표")

    if has_coordinates(event):
        lat = float(event["latitude"])
        lon = float(event["longitude"])

        coord_col1, coord_col2 = st.columns(2)

        with coord_col1:
            st.metric("위도", f"{lat:.5f}°")

        with coord_col2:
            st.metric("경도", f"{lon:.5f}°")

        # 좌표가 실제 데이터에 있을 때만 지도를 표시합니다.
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

        st.caption(
            "지도 표시는 제공처에서 제공한 좌표를 사용합니다. "
            "좌표가 사건의 정확한 피해 지점을 의미하지 않을 수도 있습니다."
        )

        map_url = (
            "https://www.openstreetmap.org/"
            f"?mlat={lat}&mlon={lon}"
            f"#map=6/{lat}/{lon}"
        )

        st.markdown(
            f"[지도에서 크게 보기 ↗]({map_url})"
        )

    else:
        st.info(
            "이 항목에는 위치 좌표가 제공되지 않았습니다. "
            "원문 자료에서 위치를 확인해 주세요."
        )

    # --------------------------------------------------------
    # C. 피해 현황
    # --------------------------------------------------------

    st.markdown("### 🚨 피해 현황")

    impact = event.get("impact") or {}

    impact_cols = st.columns(4)

    labels = ["사망자", "부상자", "이재민", "피해액"]

    for col, label in zip(impact_cols, labels):
        value = impact.get(label)

        if value is None:
            display_value = "미확인"
        elif isinstance(value, (int, float)):
            display_value = format_number(value)
        else:
            display_value = str(value)

        with col:
            st.metric(label, display_value)

    impact_source = event.get(
        "impact_source",
        "출처 정보 없음",
    )

    st.caption(f"피해 수치 출처: {impact_source}")

    if event.get("impact_verified"):
        st.success(
            "이 피해 수치는 연결된 공식 자료에서 확인된 값입니다."
        )
    elif event.get("is_news"):
        st.warning(
            "뉴스 제목·요약에서 탐지한 참고 수치입니다. "
            "공식 확정 피해 통계로 검증되지 않았으므로 "
            "원문 기사를 확인해야 합니다."
        )
    else:
        st.info(
            "현재 연결된 경보 자료에서 피해자 및 피해액의 "
            "공식 수치를 확인하지 못했습니다. "
            "미확인은 피해가 없다는 뜻이 아닙니다."
        )

    # --------------------------------------------------------
    # D. 관련 기사
    # --------------------------------------------------------

    st.markdown("### 📰 관련 기사 및 원문")

    if event_url and event_url.startswith(("https://", "http://")):
        st.markdown(
            f"[현재 사건의 원문 보기 ↗]({event_url})"
        )

    # 현재 항목과 같은 재난 유형의 뉴스 결과를 보여줍니다.
    if related_articles:
        displayed = 0
        current_url = event.get("url")

        for article in related_articles:
            article_url = article.get("url", "")

            # 현재 항목과 같은 링크는 중복 표시하지 않습니다.
            if article_url and article_url == current_url:
                continue

            article_title = article.get("title") or "제목 없음"
            article_source = article.get("source") or "출처 미확인"
            article_time = article.get("time") or "시각 미확인"

            with st.container(border=True):
                st.markdown(f"**{article_title}**")
                st.caption(
                    f"{article_source} · {article_time}"
                )

                if article_url.startswith(("https://", "http://")):
                    st.markdown(
                        f"[기사 원문 열기 ↗]({article_url})"
                    )

            displayed += 1

            if displayed >= 5:
                break

    else:
        st.write(
            "현재 검색 결과에서 관련 기사를 찾지 못했습니다."
        )

    # --------------------------------------------------------
    # E. 출처와 갱신 정보
    # --------------------------------------------------------

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
        st.markdown(
            f"[제공처 공식 사이트 ↗]({source_url})"
        )

    st.caption(
        "이 화면을 연 시각(UTC): "
        + datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    )

    st.caption(
        f"앱 캐시 기준: 최대 {CACHE_SECONDS // 60}분. "
        "위 시각은 팝업 표시 시각이며, "
        "제공처가 실제 데이터를 갱신한 시각과는 다를 수 있습니다."
    )

    # --------------------------------------------------------
    # F. 팝업 닫기
    # --------------------------------------------------------

    if st.button(
        "닫기",
        key="close_disaster_dialog",
        use_container_width=True,
    ):
        st.session_state["show_disaster_dialog"] = False
        st.session_state["selected_disaster"] = None
        st.rerun()


# ------------------------------------------------------------
# 11. URL에서 선택한 재난 유형 읽기
# ------------------------------------------------------------

try:
    selected_hazard = st.query_params.get(
        "hazard",
        "전체",
    )
except Exception:
    selected_hazard = "전체"

if isinstance(selected_hazard, list):
    selected_hazard = (
        selected_hazard[0]
        if selected_hazard
        else "전체"
    )

if selected_hazard not in HAZARDS:
    selected_hazard = "전체"


# ------------------------------------------------------------
# 12. 상단 헤더와 제목
# ------------------------------------------------------------

render_utc_header(selected_hazard)

st.markdown(
    """
    <div style="margin-top:20px">
        <div class="eyebrow">LIVE GLOBAL MONITORING</div>
        <div class="main-title">WORLD DISASTER LIVE</div>
        <div class="sub-title">
            전 세계 자연재해 경보와 최신 보도를 한곳에서 확인합니다.<br>
            UTC 시계는 초 단위로 갱신되며,
            데이터 갱신 주기는 제공처마다 다릅니다.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# 13. 데이터 수집
# ------------------------------------------------------------

with st.spinner("세계 재난 정보를 수집하고 있습니다..."):
    earthquake_events = load_earthquakes()
    gdacs_events = load_gdacs_events()
    news_events = load_news(selected_hazard)

if selected_hazard == "전체":
    primary_events = gdacs_events + earthquake_events
else:
    primary_events = [
        event for event in gdacs_events
        if event.get("kind") == selected_hazard
    ]

    if selected_hazard == "지진":
        primary_events += earthquake_events

# 링크를 기준으로 중복 경보 제거
unique_events = []
seen = set()

for event in primary_events:
    key = event.get("url") or event.get("title")

    if key and key not in seen:
        seen.add(key)
        unique_events.append(event)

primary_events = unique_events


# ------------------------------------------------------------
# 14. 요약 지표
# ------------------------------------------------------------

metric_cols = st.columns(4)

metrics = [
    (
        "선택 유형 경보",
        f"{len(primary_events):,}",
        (
            "전체 재난 경보"
            if selected_hazard == "전체"
            else f"{selected_hazard} 관련 경보"
        ),
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
        "자료 갱신 주기",
        "5분",
        "앱 캐시 기준 · 수동 갱신 가능",
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


# ------------------------------------------------------------
# 15. 자료 새로고침
# ------------------------------------------------------------

st.write("")

left, right = st.columns([3, 1])

with left:
    st.markdown(
        """
        <div class="status-line">
            ● 공개 데이터 제공처에 연결하여 자료를 조회합니다.
            연결 상태에 따라 결과가 달라질 수 있습니다.
        </div>
        """,
        unsafe_allow_html=True,
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


# ------------------------------------------------------------
# 16. 재난 경보 목록
# ------------------------------------------------------------

st.markdown(
    '<div class="section-title">'
    '📡 재난 경보 및 발생 현황'
    '</div>',
    unsafe_allow_html=True,
)

if primary_events:
    for index, event in enumerate(primary_events[:30]):
        render_event_card(
            event,
            section="alert",
            index=index,
        )
else:
    st.info(
        "현재 선택한 유형에서 표시할 경보를 찾지 못했습니다. "
        "경보가 없다는 뜻은 아니며, 제공처의 데이터 범위나 "
        "연결 상태에 따라 결과가 비어 있을 수 있습니다."
    )


# ------------------------------------------------------------
# 17. 최신 기사 목록
# ------------------------------------------------------------

st.markdown(
    '<div class="section-title">📰 최신 관련 기사</div>',
    unsafe_allow_html=True,
)

if news_events:
    st.caption(
        "기사의 발행 시각과 실제 재난 발생 시각은 다를 수 있습니다. "
        "상세 정보 버튼을 눌러 기사 및 피해 수치를 확인하세요."
    )

    for index, event in enumerate(news_events[:20]):
        render_event_card(
            event,
            section="news",
            index=index,
        )
else:
    st.warning(
        "뉴스 RSS를 불러오지 못했거나 검색 결과가 없습니다. "
        "잠시 후 다시 시도해 주세요."
    )


# ------------------------------------------------------------
# 18. 데이터 출처 안내
# ------------------------------------------------------------

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
            주요 국제 재난 이벤트와 경보 정보를 제공합니다.
        </div>
        <a href="https://www.gdacs.org/"
           target="_blank" rel="noopener noreferrer">
            GDACS 공식 사이트 ↗
        </a>
    </div>

    <div class="event-card">
        <div class="event-title">Google 뉴스 RSS</div>
        <div class="event-desc">
            재난 유형별 최신 기사 검색 결과입니다.
            중복 기사 또는 과거 사건 관련 보도가 포함될 수 있습니다.
        </div>
        <a href="https://news.google.com/"
           target="_blank" rel="noopener noreferrer">
            Google 뉴스 ↗
        </a>
    </div>

    <div class="notice">
        <b>피해 수치 이용 시 주의</b><br>
        공식 피해 수치를 확인할 수 없는 경우 미확인으로 표시합니다.
        뉴스에서 자동 탐지한 숫자는 공식 확정 통계가 아닐 수 있습니다.
        실제 대피 및 긴급 대응은 해당 지역의 공식 재난 당국 안내를
        우선으로 따르세요.
    </div>

    <div class="footer">
        WORLD DISASTER LIVE · Global natural disaster monitor<br>
        시간 기준: UTC · 시계: 브라우저에서 1초마다 갱신<br>
        재난 자료 캐시: 300초
    </div>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# 19. 선택된 재난의 중앙 팝업 열기
# ------------------------------------------------------------

if (
    st.session_state.get("show_disaster_dialog", False)
    and st.session_state.get("selected_disaster")
):
    selected_event = st.session_state["selected_disaster"]

    # 현재 선택한 재난 유형의 뉴스 목록을 팝업에 전달합니다.
    related_articles = news_events

    show_disaster_dialog(
        selected_event,
        related_articles,
    )
