```python
# main.py
# ============================================================
# 세계 자연재해 실시간 모니터링 대시보드
# 초보자도 이해하기 쉽도록 한국어 주석을 추가했습니다.
#
# 주요 기능
# 1. UTC 시계와 날짜를 초 단위로 표시
# 2. 마우스를 올리면 재난 종류 메뉴 표시
# 3. USGS 지진 데이터와 GDACS 국제 재난 경보 수집
# 4. Google 뉴스 RSS를 통한 재난 기사 검색
# 5. 기사에 공개된 피해 정보 표시
# 6. 자료 수집 실패 시 오류 안내 및 재시도
# ============================================================

import re
import html
import json
import time
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import quote

import requests
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

# 브라우저가 접근할 수 있는 공개 데이터 제공처
USGS_URL = (
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/"
    "summary/all_day.geojson"
)

GDACS_URL = "https://www.gdacs.org/xml/rss.xml"

GOOGLE_NEWS_URL = (
    "https://news.google.com/rss/search"
)

# 재난 유형별 검색어
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

# 뉴스 검색 결과에 표시할 재난 유형별 이모지
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

# 최신 기사 및 재난 자료를 주기적으로 다시 가져옵니다.
CACHE_SECONDS = 300
HTTP_TIMEOUT = 12

# 재난 데이터 요청 시 사용하는 공통 HTTP 설정
HEADERS = {
    "User-Agent": (
        "WorldDisasterDashboard/1.0 "
        "(educational Streamlit application)"
    ),
    "Accept": "application/json, application/xml, text/xml, "
              "application/rss+xml, */*",
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
            radial-gradient(ellipse at 0% 0%,
                rgba(28, 91, 133, 0.17), transparent 45%),
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
        margin: 15px 0 12px 0;
    }

    .metric-card {
        background: linear-gradient(
            145deg, rgba(25, 39, 57, 0.95),
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
        margin-bottom: 12px;
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
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# 3. UTC 시계 및 마우스 오버 메뉴
# ------------------------------------------------------------

def render_utc_header(selected_hazard):
    """
    브라우저 JavaScript로 UTC 시계를 1초마다 갱신합니다.

    시계와 날짜는 브라우저의 현재 시각을 UTC로 변환합니다.
    재난 메뉴는 시계 영역에 마우스를 올리면 나타납니다.
    메뉴를 선택하면 URL의 hazard 값이 바뀌고 앱이 다시 열립니다.
    """

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
            f'{HAZARD_ICONS[name]}&nbsp; '
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
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        background: linear-gradient(100deg, #101c2b, #0c1421);
        border: 1px solid #263c52;
        border-radius: 14px;
        padding: 13px 19px;
        min-height: 86px;
      }}

      .clock-area {{
        position: relative;
        display: inline-block;
        min-width: 0;
      }}

      .clock-label {{
        color: #80cfff;
        font-size: 10px;
        letter-spacing: 2px;
        font-weight: 800;
        margin-bottom: 6px;
      }}

      #clock {{
        font-size: clamp(23px, 3.3vw, 36px);
        font-weight: 800;
        letter-spacing: 1px;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
      }}

      .utc {{
        display: inline-block;
        color: #8ca6c0;
        font-size: 10px;
        margin-left: 6px;
        letter-spacing: 0;
        font-weight: 500;
      }}

      .date-area {{
        text-align: right;
        flex-shrink: 0;
      }}

      .date-label {{
        color: #8297ad;
        font-size: 10px;
        letter-spacing: 2px;
        margin-bottom: 8px;
      }}

      #date {{
        font-size: 14px;
        font-weight: 700;
        white-space: nowrap;
      }}

      .hover-menu {{
        display: none;
        position: absolute;
        z-index: 99999;
        top: calc(100% + 8px);
        left: 0;
        width: 215px;
        max-height: 340px;
        overflow-y: auto;
        padding: 8px;
        background: #101d2c;
        border: 1px solid #38536d;
        border-radius: 12px;
        box-shadow: 0 12px 35px rgba(0,0,0,.45);
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

      @media(max-width: 480px) {{
        .topbar {{ padding: 11px; }}
        #clock {{ font-size: 21px; }}
        .utc {{ font-size: 9px; margin-left: 2px; }}
        #date {{ font-size: 11px; }}
        .date-label {{ font-size: 9px; }}
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
          <div class="hover-menu">{menu_items}</div>
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

    components.html(header_html, height=105, scrolling=False)


# ------------------------------------------------------------
# 4. 공통 데이터 요청 함수
# ------------------------------------------------------------

def fetch_json(url, params=None):
    """JSON 자료를 가져옵니다. 실패하면 None을 반환합니다."""
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
        LOGGER.warning("JSON 자료 수집 실패: %s", exc)
        return None


def fetch_xml(url, params=None):
    """RSS/XML 자료를 가져옵니다. 실패하면 None을 반환합니다."""
    try:
        response = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        return ET.fromstring(response.content)
    except (requests.RequestException, ET.ParseError, ValueError) as exc:
        LOGGER.warning("XML 자료 수집 실패: %s", exc)
        return None


def clean_text(value):
    """HTML 태그와 불필요한 공백을 정리합니다."""
    if not value:
        return ""

    value = re.sub(r"<[^>]+>", " ", str(value))
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def parse_utc(value):
    """UTC 시각을 화면 표시용 문자열로 변환합니다."""
    if value is None:
        return "시각 정보 없음"

    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        else:
            text_value = str(value).strip()
            dt = datetime.fromisoformat(
                text_value.replace("Z", "+00:00")
            )

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            dt = dt.astimezone(timezone.utc)

        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError, OverflowError, OSError):
        return "시각 정보 없음"


# ------------------------------------------------------------
# 5. USGS 실시간 지진 자료
# ------------------------------------------------------------

@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def load_earthquakes():
    """
    USGS 최근 24시간 지진 GeoJSON을 가져옵니다.

    규모, 장소, 깊이, 발생 시각, 진동을 느꼈다고 보고한
    횟수 등을 제공처의 데이터 그대로 사용합니다.
    """

    data = fetch_json(USGS_URL)

    if not isinstance(data, dict):
        return []

    features = data.get("features", [])
    events = []

    for feature in features:
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []

        try:
            magnitude = properties.get("mag")
            longitude = coordinates[0] if len(coordinates) > 0 else None
            latitude = coordinates[1] if len(coordinates) > 1 else None
            depth = coordinates[2] if len(coordinates) > 2 else None

            place = properties.get("place") or "위치 정보 없음"
            event_time = properties.get("time")
            felt = properties.get("felt")

            if magnitude is not None:
                magnitude_text = f"규모 {float(magnitude):.1f}"
            else:
                magnitude_text = "규모 미집계"

            details = [
                magnitude_text,
                f"위치: {place}",
                f"발생: {parse_utc(event_time)}",
            ]

            if depth is not None:
                details.append(f"깊이: {depth:g} km")

            if felt is not None:
                details.append(f"진동 신고: {felt:,}건")

            events.append({
                "kind": "지진",
                "title": f"지진 — {place}",
                "time_raw": event_time or 0,
                "time": parse_utc(event_time),
                "location": place,
                "description": " · ".join(details),
                "source": "USGS",
                "url": properties.get("url") or
                       "https://earthquake.usgs.gov/earthquakes/map/",
                "magnitude": magnitude,
                "felt": felt,
                "latitude": latitude,
                "longitude": longitude,
                "depth": depth,
                "impact": {
                    "사망자": None,
                    "부상자": None,
                    "이재민": None,
                    "피해액": None,
                },
            })

        except (TypeError, ValueError, IndexError) as exc:
            LOGGER.warning("지진 항목 변환 실패: %s", exc)
            continue

    events.sort(
        key=lambda event: event.get("time_raw") or 0,
        reverse=True,
    )

    return events


# ------------------------------------------------------------
# 6. GDACS 국제 재난 경보
# ------------------------------------------------------------

def classify_gdacs(title, description, category=""):
    """GDACS 항목의 제목과 설명을 보고 재난 유형을 분류합니다."""

    text_value = (
        f"{title} {description} {category}"
    ).lower()

    # 영문 키워드를 이용한 간단한 분류입니다.
    # 분류되지 않는 사건은 전체 목록에서 확인할 수 있습니다.
    rules = [
        ("태풍", ["cyclone", "typhoon", "hurricane", "tropical storm"]),
        ("지진", ["earthquake", "seismic"]),
        ("산불", ["forest fire", "wildfire", "fire"]),
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
    """
    GDACS RSS 피드를 읽어 국제 재난 경보를 가져옵니다.

    RSS 항목에 들어 있는 정보만 표시하며,
    피해 규모를 임의로 계산하거나 만들어 내지 않습니다.
    """

    root = fetch_xml(GDACS_URL)

    if root is None:
        return []

    events = []

    for item in root.findall(".//item"):
        try:
            title = clean_text(item.findtext("title", "제목 없음"))
            description = clean_text(
                item.findtext("description", "")
            )
            link = clean_text(item.findtext("link", ""))
            pub_date = clean_text(item.findtext("pubDate", ""))

            category = ""
            for child in item:
                if child.tag.lower().endswith("category"):
                    category = clean_text(child.text or "")
                    break

            kind = classify_gdacs(title, description, category)

            # GDACS RSS에 기록된 경보 등급을 찾아봅니다.
            # 등급 정보가 없으면 표시하지 않습니다.
            alert_level = "경보 등급 정보 없음"
            combined = f"{title} {description}"

            if re.search(r"\bRed\b", combined, flags=re.I):
                alert_level = "적색 경보"
            elif re.search(r"\bOrange\b", combined, flags=re.I):
                alert_level = "주황색 경보"
            elif re.search(r"\bGreen\b", combined, flags=re.I):
                alert_level = "녹색 경보"

            events.append({
                "kind": kind,
                "title": title,
                "time_raw": pub_date,
                "time": pub_date or "시각 정보 없음",
                "location": "국제 재난 경보",
                "description": description,
                "source": "GDACS",
                "url": link,
                "alert_level": alert_level,
                "impact": {
                    "사망자": None,
                    "부상자": None,
                    "이재민": None,
                    "피해액": None,
                },
            })

        except (AttributeError, TypeError, ValueError) as exc:
            LOGGER.warning("GDACS 항목 변환 실패: %s", exc)
            continue

    return events


# ------------------------------------------------------------
# 7. Google 뉴스 RSS
# ------------------------------------------------------------

@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def load_news(hazard):
    """
    선택한 재난 유형에 맞는 최신 뉴스 RSS를 가져옵니다.

    뉴스는 사건을 파악하는 참고 자료입니다.
    기사에 나온 수치가 공식 확정 통계라는 의미는 아닙니다.
    """

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
            description = clean_text(
                item.findtext("description", "")
            )

            # RSS에서 제공하는 출처 정보가 있으면 추출합니다.
            source_name = "Google 뉴스 RSS"
            source_node = item.find("source")

            if source_node is not None and source_node.text:
                source_name = clean_text(source_node.text)

            # Google 뉴스 검색 결과는 선택한 검색 유형을 기준으로 표시합니다.
            # 검색 결과가 실제 공식 재난 경보임을 뜻하지는 않습니다.
            events.append({
                "kind": hazard,
                "title": title,
                "time_raw": pub_date,
                "time": pub_date or "발행 시각 정보 없음",
                "location": "기사에서 확인",
                "description": description or
                               "기사 요약이 제공되지 않았습니다.",
                "source": source_name,
                "url": link,
                "impact": extract_impact_numbers(
                    f"{title}. {description}"
                ),
                "is_news": True,
            })

        except (AttributeError, TypeError, ValueError) as exc:
            LOGGER.warning("뉴스 항목 변환 실패: %s", exc)
            continue

    return events


# ------------------------------------------------------------
# 8. 기사 요약에서 피해 수치 찾기
# ------------------------------------------------------------

def extract_impact_numbers(text_value):
    """
    뉴스 제목과 RSS 요약에 명시된 피해 숫자를 보조적으로 찾습니다.

    주의:
    - 짧은 뉴스 요약만 분석하므로 놓치는 숫자가 있을 수 있습니다.
    - 숫자가 발견되어도 문맥상 확정된 피해인지 자동으로 보장할 수 없습니다.
    - 따라서 결과는 '기사 요약에서 탐지한 수치'로만 표시합니다.
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
        match = re.search(pattern, text_value, flags=re.I)

        if match:
            try:
                result[label] = int(match.group(1).replace(",", ""))
            except (ValueError, TypeError):
                result[label] = None

    # 피해액은 통화 단위와 기준이 다양하므로 자동 환산하지 않습니다.
    money_match = re.search(
        r"(?:\$|USD\s*)([\d,.]+\s*(?:billion|million|trillion|bn|mn)?)",
        text_value,
        flags=re.I,
    )

    if money_match:
        result["피해액"] = money_match.group(0)

    return result


# ------------------------------------------------------------
# 9. 화면 표시용 HTML 안전 처리
# ------------------------------------------------------------

def safe(value):
    """HTML에 표시할 문자열을 안전하게 변환합니다."""
    return html.escape(str(value or ""))


def format_number(value):
    """숫자가 있으면 천 단위 쉼표를 표시합니다."""
    if value is None:
        return "미집계"

    try:
        return f"{int(value):,}"
    except (ValueError, TypeError, OverflowError):
        return str(value)


def render_event_card(event):
    """재난 또는 기사 한 건을 카드 형태로 보여줍니다."""

    title = safe(event.get("title", "제목 없음"))
    source = safe(event.get("source", "출처 정보 없음"))
    description = safe(event.get("description", ""))
    event_time = safe(event.get("time", "시각 정보 없음"))
    link = event.get("url", "")

    if not isinstance(link, str) or not link.startswith(
        ("https://", "http://")
    ):
        link = ""

    # 피해 숫자는 데이터 제공처 또는 기사 요약에서
    # 실제로 찾은 경우에만 표시합니다.
    impact = event.get("impact") or {}

    impact_parts = []

    for label in ("사망자", "부상자", "이재민", "피해액"):
        value = impact.get(label)

        if value is not None:
            if isinstance(value, (int, float)):
                display_value = format_number(value)
            else:
                display_value = str(value)

            impact_parts.append(
                f"{safe(label)}: {safe(display_value)}"
            )
        else:
            impact_parts.append(f"{safe(label)}: 미집계")

    impact_html = " &nbsp;·&nbsp; ".join(impact_parts)

    alert = event.get("alert_level")

    alert_html = ""

    if alert:
        alert_html = (
            '<div class="event-meta">경보: '
            + safe(alert)
            + "</div>"
        )

    if event.get("is_news"):
        impact_note = (
            "기사 제목·요약에서 탐지한 참고 수치이며, "
            "공식 피해 통계로 검증된 값이 아닐 수 있습니다."
        )
    else:
        impact_note = (
            "공식 피해 숫자가 해당 데이터에 없으면 "
            "미집계로 표시합니다."
        )

    link_html = ""

    if link:
        link_html = (
            '<div style="margin-top:12px">'
            f'<a href="{html.escape(link, quote=True)}" '
            'target="_blank" rel="noopener noreferrer">'
            '원문 및 자료 확인 ↗</a></div>'
        )

    st.markdown(
        f"""
        <div class="event-card">
            <div class="source-tag">{source}</div>
            <div class="event-title">{title}</div>
            <div class="event-meta">🕒 {event_time}</div>
            {alert_html}
            <div class="event-desc">{description}</div>
            <div class="event-meta" style="margin-top:12px">
                <b>피해 현황</b><br>
                {impact_html}
            </div>
            <div class="event-meta" style="margin-top:7px">
                {safe(impact_note)}
            </div>
            {link_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------
# 10. 선택한 재난 유형 읽기
# ------------------------------------------------------------

try:
    query_hazard = st.query_params.get("hazard", "전체")
except Exception:
    query_hazard = "전체"

if isinstance(query_hazard, list):
    query_hazard = query_hazard[0] if query_hazard else "전체"

if query_hazard not in HAZARDS:
    query_hazard = "전체"

selected_hazard = query_hazard


# ------------------------------------------------------------
# 11. 상단 헤더
# ------------------------------------------------------------

render_utc_header(selected_hazard)

st.markdown(
    """
    <div style="margin-top:20px">
        <div class="eyebrow">LIVE GLOBAL MONITORING</div>
        <div class="main-title">WORLD DISASTER LIVE</div>
        <div class="sub-title">
            전 세계 자연재해 경보와 최신 보도를 한곳에서 확인합니다.<br>
            실시간 시계는 UTC 기준이며, 각 데이터의 실제 갱신 주기는
            제공처마다 다릅니다.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# 12. 데이터 불러오기
# ------------------------------------------------------------

with st.spinner("세계 재난 정보를 수집하고 있습니다..."):
    earthquake_events = load_earthquakes()
    gdacs_events = load_gdacs_events()
    news_events = load_news(selected_hazard)

# 선택한 유형에 맞춰 자료를 구분합니다.
if selected_hazard == "전체":
    primary_events = gdacs_events + earthquake_events
else:
    primary_events = [
        event for event in gdacs_events
        if event.get("kind") == selected_hazard
    ]

    if selected_hazard == "지진":
        primary_events += earthquake_events

# 동일 링크가 여러 번 등장하지 않도록 중복을 제거합니다.
unique_events = []
seen = set()

for event in primary_events:
    key = event.get("url") or event.get("title")

    if key and key not in seen:
        seen.add(key)
        unique_events.append(event)

primary_events = unique_events


# ------------------------------------------------------------
# 13. 요약 지표
# ------------------------------------------------------------

total_alerts = len(primary_events)
total_articles = len(news_events)

if selected_hazard == "전체":
    data_label = "전체 재난 경보"
else:
    data_label = f"{selected_hazard} 관련 경보"

metric_cols = st.columns(4)

metrics = [
    (
        "선택 유형 경보",
        format_number(total_alerts),
        data_label,
    ),
    (
        "최근 지진",
        format_number(len(earthquake_events)),
        "USGS 최근 24시간",
    ),
    (
        "관련 기사",
        format_number(total_articles),
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
# 14. 자료 갱신 버튼과 상태 표시
# ------------------------------------------------------------

st.write("")

left, right = st.columns([3, 1])

with left:
    st.markdown(
        """
        <div class="status-line">
            ● 데이터 제공처에 연결하여 자료를 조회합니다.
            연결 상태와 검색 결과는 요청할 때마다 달라질 수 있습니다.
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
# 15. 재난 경보 목록
# ------------------------------------------------------------

st.markdown(
    '<div class="section-title">📡 재난 경보 및 발생 현황</div>',
    unsafe_allow_html=True,
)

if primary_events:
    for event in primary_events[:30]:
        render_event_card(event)
else:
    st.info(
        "현재 선택한 유형에서 표시할 공식 경보를 찾지 못했습니다. "
        "경보가 없다는 뜻은 아니며, 데이터 제공처의 범위나 연결 상태에 "
        "따라 결과가 비어 있을 수 있습니다."
    )


# ------------------------------------------------------------
# 16. 최신 뉴스 기사
# ------------------------------------------------------------

st.markdown(
    '<div class="section-title">📰 최신 관련 기사</div>',
    unsafe_allow_html=True,
)

if news_events:
    st.caption(
        "뉴스 검색 결과는 보도 내용을 빠르게 확인하기 위한 참고 자료입니다. "
        "기사의 발행 시각과 재난 발생 시각은 다를 수 있습니다."
    )

    for event in news_events[:20]:
        render_event_card(event)
else:
    st.warning(
        "뉴스 RSS를 불러오지 못했거나 검색 결과가 없습니다. "
        "잠시 후 다시 시도하거나 재난 경보 목록을 확인해 주세요."
    )


# ------------------------------------------------------------
# 17. 데이터 제공처 안내
# ------------------------------------------------------------

st.markdown(
    """
    <div class="section-title">🔎 데이터 출처 및 해석 안내</div>
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
            주요 국제 재난 이벤트와 경보 정보를 제공하는 시스템입니다.
            모든 지역의 모든 재난을 빠짐없이 기록하는 시스템은 아닙니다.
        </div>
        <a href="https://www.gdacs.org/"
           target="_blank" rel="noopener noreferrer">
           GDACS 공식 사이트 ↗
        </a>
    </div>
    <div class="event-card">
        <div class="event-title">Google 뉴스 RSS</div>
        <div class="event-desc">
            선택한 재난 유형의 최신 보도 검색 결과입니다.
            검색 결과에는 중복 기사, 후속 보도, 과거 사건 관련 기사가
            포함될 수 있습니다.
        </div>
        <a href="https://news.google.com/"
           target="_blank" rel="noopener noreferrer">
           Google 뉴스 ↗
        </a>
    </div>

    <div class="notice">
        <b>피해 수치 이용 시 주의</b><br>
        사망자, 부상자, 이재민, 재산 피해액은 집계 기관과 발표 시점에 따라
        달라집니다. 이 앱은 출처에서 제공하지 않는 숫자를 임의로 생성하지
        않습니다. 뉴스 요약에서 자동으로 찾은 수치는 문맥 검증이 완료된
        공식 통계가 아니므로 원문 기사와 공식 기관 발표를 확인하세요.<br><br>
        이 앱은 정보 확인용이며, 대피 여부나 긴급 행동은 해당 지역의
        공식 재난 당국 안내를 우선으로 따르세요.
    </div>

    <div class="footer">
        WORLD DISASTER LIVE · Global natural disaster monitor<br>
        시간 기준: UTC · 시계: 브라우저에서 1초마다 갱신<br>
        재난 자료 캐시: 300초 · 뉴스 발행 시각과 재난 발생 시각은 다를 수 있음
    </div>
    """,
    unsafe_allow_html=True,
)
```
