
import re
import html
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components


# =========================================================
# 기본 설정
# =========================================================
st.set_page_config(
    page_title="WORLD DISASTER LIVE",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

logging.basicConfig(level=logging.ERROR)

REQUEST_TIMEOUT = 15

USGS_URL = (
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/"
    "summary/all_day.geojson"
)
GDACS_URL = "https://www.gdacs.org/xml/rss.xml"
GOOGLE_NEWS_URL = "https://news.google.com/rss/search"

HAZARDS = [
    ("All", "ALL"),
    ("Typhoon", "TYPHOON"),
    ("Earthquake", "EARTHQUAKE"),
    ("Wildfire", "WILDFIRE"),
    ("Flood", "FLOOD"),
    ("Heavy Rain", "HEAVY_RAIN"),
    ("Drought", "DROUGHT"),
    ("Heavy Snow", "HEAVY_SNOW"),
    ("Heatwave", "HEATWAVE"),
    ("Cold Wave", "COLD_WAVE"),
    ("Landslide", "LANDSLIDE"),
]

HAZARD_KEYWORDS = {
    "TYPHOON": [
        "typhoon", "hurricane", "cyclone", "tropical storm",
        "tropical cyclone", "태풍", "허리케인", "사이클론",
    ],
    "EARTHQUAKE": [
        "earthquake", "seismic", "aftershock", "지진",
    ],
    "WILDFIRE": [
        "wildfire", "forest fire", "bushfire", "wild fire",
        "산불", "산림 화재",
    ],
    "FLOOD": [
        "flood", "flash flood", "flooding", "inundation",
        "홍수", "침수",
    ],
    "HEAVY_RAIN": [
        "heavy rain", "torrential rain", "rainfall",
        "downpour", "monsoon rain", "폭우", "집중호우",
    ],
    "DROUGHT": [
        "drought", "water shortage", "가뭄",
    ],
    "HEAVY_SNOW": [
        "heavy snow", "snowstorm", "blizzard", "snowfall",
        "폭설", "눈보라",
    ],
    "HEATWAVE": [
        "heatwave", "heat wave", "extreme heat",
        "record temperature", "폭염",
    ],
    "COLD_WAVE": [
        "cold wave", "extreme cold", "cold snap",
        "freeze warning", "한파",
    ],
    "LANDSLIDE": [
        "landslide", "mudslide", "rockslide",
        "산사태", "토석류",
    ],
}

HAZARD_LABELS = dict(HAZARDS)

HAZARD_COLORS = {
    "TYPHOON": "#7c3aed",
    "EARTHQUAKE": "#dc2626",
    "WILDFIRE": "#ea580c",
    "FLOOD": "#2563eb",
    "HEAVY_RAIN": "#0891b2",
    "DROUGHT": "#ca8a04",
    "HEAVY_SNOW": "#64748b",
    "HEATWAVE": "#e11d48",
    "COLD_WAVE": "#0284c7",
    "LANDSLIDE": "#92400e",
    "ALL": "#64748b",
}


# =========================================================
# 스타일
# =========================================================
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 0.8rem;
        padding-bottom: 2rem;
        max-width: 1500px;
    }

    h1, h2, h3 {
        letter-spacing: -0.4px;
    }

    .section-title {
        font-size: 1.25rem;
        font-weight: 800;
        margin: 1rem 0 0.7rem 0;
    }

    .event-card {
        border: 1px solid #303744;
        border-radius: 14px;
        padding: 17px;
        min-height: 180px;
        background: #151b26;
        margin-bottom: 8px;
    }

    .event-type {
        font-size: 0.75rem;
        font-weight: 800;
        letter-spacing: 1px;
        margin-bottom: 8px;
    }

    .event-title {
        font-size: 1.03rem;
        font-weight: 750;
        line-height: 1.4;
        margin-bottom: 10px;
        overflow-wrap: anywhere;
    }

    .event-meta {
        color: #aab4c4;
        font-size: 0.83rem;
        line-height: 1.7;
    }

    .metric-panel {
        border: 1px solid #303744;
        border-radius: 12px;
        padding: 14px 16px;
        background: #151b26;
    }

    .small-muted {
        color: #9ca3af;
        font-size: 0.82rem;
    }

    div[data-testid="stButton"] > button {
        border-radius: 8px;
        font-weight: 650;
        min-height: 42px;
        width: 100%;
    }

    div[data-testid="stLinkButton"] > a {
        border-radius: 8px;
    }

    hr {
        border-color: #303744;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# UTC 시계
# 시계는 HTML로 표시하지만 재난 메뉴는 아래의
# Streamlit 버튼으로 만들어 실제 클릭 동작을 보장한다.
# =========================================================
def render_utc_header():
    components.html(
        """
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            * { box-sizing: border-box; }
            html, body {
                margin: 0;
                padding: 0;
                width: 100%;
                background: transparent;
                color: #f9fafb;
                font-family: Arial, Helvetica, sans-serif;
            }
            .header {
                display: grid;
                grid-template-columns: 1fr auto 1fr;
                align-items: center;
                width: 100%;
                padding: 16px 8px 12px;
                min-height: 118px;
            }
            .clock-area {
                grid-column: 2;
                text-align: center;
            }
            #clock {
                font-size: clamp(42px, 7vw, 76px);
                font-weight: 800;
                line-height: 1.08;
                letter-spacing: 2px;
                white-space: nowrap;
            }
            .utc {
                font-size: 12px;
                color: #9ca3af;
                letter-spacing: 3px;
                margin-top: 7px;
            }
            #date {
                grid-column: 3;
                justify-self: end;
                text-align: right;
                color: #cbd5e1;
                font-size: 15px;
                white-space: nowrap;
            }
            @media (max-width: 600px) {
                .header {
                    grid-template-columns: 1fr;
                    gap: 8px;
                    padding-top: 10px;
                }
                .clock-area {
                    grid-column: 1;
                }
                #date {
                    grid-column: 1;
                    justify-self: center;
                    text-align: center;
                }
                #clock {
                    font-size: 48px;
                }
            }
        </style>
        </head>
        <body>
            <div class="header">
                <div class="clock-area">
                    <div id="clock">00:00:00</div>
                    <div class="utc">UTC</div>
                </div>
                <div id="date">0000-00-00 UTC</div>
            </div>

            <script>
                function updateClock() {
                    const now = new Date();
                    const pad = n => String(n).padStart(2, "0");

                    document.getElementById("clock").textContent =
                        pad(now.getUTCHours()) + ":" +
                        pad(now.getUTCMinutes()) + ":" +
                        pad(now.getUTCSeconds());

                    document.getElementById("date").textContent =
                        now.getUTCFullYear() + "-" +
                        pad(now.getUTCMonth() + 1) + "-" +
                        pad(now.getUTCDate()) + " UTC";
                }

                updateClock();
                setInterval(updateClock, 1000);
            </script>
        </body>
        </html>
        """,
        height=125,
        scrolling=False,
    )


# =========================================================
# 메뉴 버튼
# 각 버튼은 session_state를 변경하고 앱을 다시 실행한다.
# =========================================================
def render_hazard_menu():
    st.markdown(
        """
        <div style="
            width:100%;
            padding:8px 0 3px;
            font-size:12px;
            font-weight:800;
            color:#9ca3af;
            letter-spacing:1.5px;
        ">SELECT DISASTER TYPE</div>
        """,
        unsafe_allow_html=True,
    )

    # 버튼을 6개 + 5개로 배치해 가로폭을 넓게 사용한다.
    rows = [HAZARDS[:6], HAZARDS[6:]]

    for row_index, row in enumerate(rows):
        columns = st.columns(len(row), gap="small")

        for col, (label, code) in zip(columns, row):
            with col:
                is_active = st.session_state.get("hazard", "ALL") == code

                button_label = label
                if is_active:
                    button_label = f"● {label}"

                if st.button(
                    button_label,
                    key=f"hazard_button_{code}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    st.session_state["hazard"] = code
                    st.session_state.pop("selected_event", None)
                    st.rerun()


# =========================================================
# 공통 유틸리티
# =========================================================
def safe_text(value, default="Unknown"):
    if value is None:
        return default
    value = str(value).strip()
    return value if value else default


def parse_datetime(value):
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def format_utc(value):
    dt = parse_datetime(value)
    if not dt:
        return "Unknown"
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def fetch_text(url, params=None):
    headers = {
        "User-Agent": "WorldDisasterLive/1.0 (public information dashboard)"
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        logging.error("Request failed for %s: %s", url, exc)
        return None


def fetch_json(url):
    text = fetch_text(url)
    if not text:
        return None

    try:
        import json
        return json.loads(text)
    except ValueError:
        return None


def clean_html_text(value):
    value = safe_text(value, "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def classify_hazard(text):
    lower_text = (text or "").lower()

    for hazard_code, keywords in HAZARD_KEYWORDS.items():
        if any(keyword.lower() in lower_text for keyword in keywords):
            return hazard_code

    return "ALL"


def get_coordinates(event):
    lat = event.get("latitude")
    lon = event.get("longitude")

    try:
        if lat is None or lon is None:
            return None
        lat = float(lat)
        lon = float(lon)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        return lat, lon
    except (TypeError, ValueError):
        return None


# =========================================================
# Earthquake feed: USGS
# =========================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_earthquakes():
    payload = fetch_json(USGS_URL)
    events = []

    if not payload:
        return events

    for feature in payload.get("features", []):
        properties = feature.get("properties", {}) or {}
        geometry = feature.get("geometry", {}) or {}
        coordinates = geometry.get("coordinates", [])

        lon = coordinates[0] if len(coordinates) > 0 else None
        lat = coordinates[1] if len(coordinates) > 1 else None
        depth = coordinates[2] if len(coordinates) > 2 else None

        timestamp_ms = properties.get("time")
        event_time = None

        if timestamp_ms is not None:
            event_time = datetime.fromtimestamp(
                timestamp_ms / 1000,
                tz=timezone.utc,
            ).isoformat()

        magnitude = properties.get("mag")
        place = safe_text(properties.get("place"), "Location unavailable")

        events.append({
            "id": str(feature.get("id", properties.get("url", place))),
            "title": f"M{magnitude} Earthquake — {place}",
            "hazard": "EARTHQUAKE",
            "location": place,
            "time": event_time,
            "source": "USGS",
            "source_url": properties.get("url"),
            "latitude": lat,
            "longitude": lon,
            "magnitude": magnitude,
            "depth_km": depth,
            "felt": properties.get("felt"),
            "alert": properties.get("alert"),
            "description": safe_text(properties.get("title"), place),
            "damage": "Not confirmed by this feed",
        })

    events.sort(
        key=lambda item: item.get("time") or "",
        reverse=True,
    )
    return events


# =========================================================
# GDACS RSS
# =========================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_gdacs_events():
    xml_text = fetch_text(GDACS_URL)
    events = []

    if not xml_text:
        return events

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return events

    for item in root.findall(".//item"):
        title = clean_html_text(item.findtext("title", ""))
        description = clean_html_text(item.findtext("description", ""))
        link = safe_text(item.findtext("link"), "")
        pub_date = item.findtext("pubDate", "")

        combined = f"{title} {description}"
        hazard = classify_hazard(combined)

        if hazard == "ALL":
            continue

        event_time = None
        if pub_date:
            try:
                from email.utils import parsedate_to_datetime
                parsed = parsedate_to_datetime(pub_date)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                event_time = parsed.astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError, OverflowError):
                event_time = None

        events.append({
            "id": link or title,
            "title": title or "GDACS disaster report",
            "hazard": hazard,
            "location": "See source report",
            "time": event_time,
            "source": "GDACS",
            "source_url": link,
            "latitude": None,
            "longitude": None,
            "magnitude": None,
            "depth_km": None,
            "felt": None,
            "alert": "See source report",
            "description": description or title,
            "damage": "Check the official source",
        })

    events.sort(
        key=lambda item: item.get("time") or "",
        reverse=True,
    )
    return events


# =========================================================
# News RSS
# =========================================================
def google_news_query(hazard):
    queries = {
        "ALL": "global natural disaster OR earthquake OR typhoon OR wildfire",
        "TYPHOON": "typhoon OR hurricane OR tropical cyclone",
        "EARTHQUAKE": "earthquake",
        "WILDFIRE": "wildfire OR forest fire",
        "FLOOD": "flood OR flash flood",
        "HEAVY_RAIN": "heavy rain OR torrential rain",
        "DROUGHT": "drought",
        "HEAVY_SNOW": "heavy snow OR blizzard",
        "HEATWAVE": "heatwave OR extreme heat",
        "COLD_WAVE": "cold wave OR extreme cold",
        "LANDSLIDE": "landslide OR mudslide",
    }
    return queries.get(hazard, queries["ALL"])


@st.cache_data(ttl=300, show_spinner=False)
def load_news(hazard):
    query = google_news_query(hazard)

    params = {
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }

    xml_text = fetch_text(GOOGLE_NEWS_URL, params=params)
    articles = []

    if not xml_text:
        return articles

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return articles

    for item in root.findall(".//item"):
        title = clean_html_text(item.findtext("title", ""))
        description = clean_html_text(item.findtext("description", ""))
        link = safe_text(item.findtext("link"), "")
        source = item.find("source")
        source_name = (
            clean_html_text(source.text)
            if source is not None and source.text
            else "Google News"
        )

        pub_date = item.findtext("pubDate", "")
        event_time = None

        if pub_date:
            try:
                from email.utils import parsedate_to_datetime
                parsed = parsedate_to_datetime(pub_date)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                event_time = parsed.astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError, OverflowError):
                event_time = None

        classified = classify_hazard(f"{title} {description}")

        articles.append({
            "title": title or "Untitled report",
            "description": description,
            "url": link,
            "source": source_name,
            "time": event_time,
            "hazard": classified,
        })

    # Avoid duplicate links
    unique = {}
    for article in articles:
        unique[article["url"] or article["title"]] = article

    articles = list(unique.values())
    articles.sort(
        key=lambda item: item.get("time") or "",
        reverse=True,
    )
    return articles[:40]


# =========================================================
# Display helpers
# =========================================================
def get_hazard_label(code):
    return HAZARD_LABELS.get(code, code.replace("_", " ").title())


def event_card(event, index):
    hazard = event.get("hazard", "ALL")
    color = HAZARD_COLORS.get(hazard, "#64748b")
    title = html.escape(safe_text(event.get("title"), "Untitled event"))
    location = html.escape(safe_text(event.get("location"), "Unknown"))
    source = html.escape(safe_text(event.get("source"), "Unknown"))
    time_text = html.escape(format_utc(event.get("time")))
    hazard_label = html.escape(get_hazard_label(hazard))

    st.markdown(
        f"""
        <div class="event-card">
            <div class="event-type" style="color:{color}">
                {hazard_label.upper()}
            </div>
            <div class="event-title">{title}</div>
            <div class="event-meta">
                Location: {location}<br>
                Time: {time_text}<br>
                Source: {source}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "View Details",
        key=f"details_{index}_{event.get('id', title)}",
        use_container_width=True,
    ):
        st.session_state["selected_event"] = event
        st.rerun()


def article_card(article, index):
    title = safe_text(article.get("title"), "Untitled report")
    source = safe_text(article.get("source"), "News source")

    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.caption(
            f"{source} · {format_utc(article.get('time'))}"
        )

        if article.get("description"):
            st.write(article["description"][:350])

        if article.get("url"):
            st.link_button(
                "Open Article",
                article["url"],
                use_container_width=True,
            )


# =========================================================
# Event details dialog
# =========================================================
@st.dialog("Disaster Details", width="large")
def show_disaster_dialog(event):
    hazard = event.get("hazard", "ALL")
    color = HAZARD_COLORS.get(hazard, "#64748b")

    st.markdown(
        f"""
        <div style="
            color:{color};
            font-size:12px;
            font-weight:800;
            letter-spacing:1.4px;
        ">{html.escape(get_hazard_label(hazard).upper())}</div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader(safe_text(event.get("title"), "Untitled event"))

    st.markdown("### Basic Information")
    col1, col2 = st.columns(2)

    with col1:
        st.write("**Location**")
        st.write(safe_text(event.get("location")))
        st.write("**Reported time**")
        st.write(format_utc(event.get("time")))

    with col2:
        st.write("**Data source**")
        st.write(safe_text(event.get("source")))
        st.write("**Alert level**")
        st.write(safe_text(event.get("alert"), "Unconfirmed"))

    if hazard == "EARTHQUAKE":
        st.markdown("### Earthquake Measurements")

        mag = event.get("magnitude")
        depth = event.get("depth_km")
        felt = event.get("felt")

        m1, m2, m3 = st.columns(3)

        m1.metric(
            "Magnitude",
            f"{mag}" if mag is not None else "Unknown",
        )
        m2.metric(
            "Depth",
            f"{depth} km" if depth is not None else "Unknown",
        )
        m3.metric(
            "Felt reports",
            f"{felt}" if felt is not None else "Unknown",
        )

    st.markdown("### Damage and Impact")
    st.info(
        "Confirmed casualty and damage totals are not available "
        "from the selected feed. Check the original report for "
        "verified figures."
    )
    st.write("**Damage status:** Not confirmed by this dashboard.")
    st.write("**Casualties:** Unknown")
    st.write("**Economic losses:** Unknown")

    if event.get("description"):
        st.markdown("### Report Summary")
        st.write(event["description"])

    coordinates = get_coordinates(event)
    if coordinates:
        lat, lon = coordinates

        st.markdown("### Location Map")
        st.caption(f"Coordinates: {lat:.4f}, {lon:.4f}")

        map_data = pd.DataFrame({
            "latitude": [lat],
            "longitude": [lon],
        })
        st.map(map_data, zoom=5)

    st.markdown("### Source")
    if event.get("source_url"):
        st.link_button(
            "Open Original Source",
            event["source_url"],
            use_container_width=True,
        )
    else:
        st.write("Original source link is unavailable.")

    st.caption(
        "Times are displayed in UTC. Information may change as "
        "official agencies update their reports."
    )


# =========================================================
# Filtering
# =========================================================
def filter_events(events, selected_hazard):
    if selected_hazard == "ALL":
        return events

    return [
        event for event in events
        if event.get("hazard") == selected_hazard
    ]


def filter_articles(articles, selected_hazard):
    if selected_hazard == "ALL":
        return articles

    keywords = HAZARD_KEYWORDS.get(selected_hazard, [])

    filtered = []
    for article in articles:
        text = (
            str(article.get("title", "")) + " " +
            str(article.get("description", ""))
        ).lower()

        if article.get("hazard") == selected_hazard or any(
            keyword.lower() in text for keyword in keywords
        ):
            filtered.append(article)

    return filtered


# =========================================================
# Main app
# =========================================================
if "hazard" not in st.session_state:
    st.session_state["hazard"] = "ALL"

render_utc_header()

st.markdown(
    """
    <div style="text-align:center; padding:0 0 12px 0;">
        <div style="
            font-size:clamp(25px, 4vw, 40px);
            font-weight:900;
            letter-spacing:1px;
        ">WORLD DISASTER LIVE</div>
        <div style="color:#9ca3af; font-size:14px; margin-top:4px;">
            Global natural disaster monitoring dashboard
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

render_hazard_menu()

selected_hazard = st.session_state["hazard"]

st.divider()

left, right = st.columns([4, 1])

with left:
    if selected_hazard == "ALL":
        st.subheader("Latest Global Disaster Reports")
    else:
        st.subheader(f"{get_hazard_label(selected_hazard)} Reports")

with right:
    if st.button("Refresh Data", use_container_width=True):
        load_earthquakes.clear()
        load_gdacs_events.clear()
        load_news.clear()
        st.session_state.pop("selected_event", None)
        st.rerun()


with st.spinner("Loading disaster reports..."):
    earthquakes = load_earthquakes()
    gdacs_events = load_gdacs_events()
    all_events = earthquakes + gdacs_events

    # Keep the event list free of duplicate IDs.
    deduped = {}
    for event in all_events:
        deduped[event.get("id", event.get("title", ""))] = event
    all_events = list(deduped.values())

    all_events.sort(
        key=lambda item: item.get("time") or "",
        reverse=True,
    )

    filtered_events = filter_events(all_events, selected_hazard)

    # Query news for the selected hazard, then filter again
    # using the same selected category.
    all_articles = load_news(selected_hazard)
    filtered_articles = filter_articles(
        all_articles,
        selected_hazard,
    )


# Summary metrics
total_events = len(filtered_events)
total_articles = len(filtered_articles)
earthquake_count = sum(
    1 for event in filtered_events
    if event.get("hazard") == "EARTHQUAKE"
)

m1, m2, m3 = st.columns(3)

with m1:
    st.metric("Disaster Reports", total_events)

with m2:
    st.metric("Related News Articles", total_articles)

with m3:
    st.metric("Earthquake Reports", earthquake_count)


st.markdown('<div class="section-title">Live Events</div>', unsafe_allow_html=True)

if not filtered_events:
    st.info(
        f"No matching {get_hazard_label(selected_hazard)} events "
        "were found in the currently available feeds. Try Refresh Data "
        "or select another category."
    )
else:
    # Show up to 30 event cards.
    display_events = filtered_events[:30]

    for start in range(0, len(display_events), 3):
        event_row = display_events[start:start + 3]
        columns = st.columns(3, gap="medium")

        for offset, (column, event) in enumerate(
            zip(columns, event_row)
        ):
            with column:
                event_card(event, start + offset)


st.divider()
st.markdown(
    '<div class="section-title">Related News</div>',
    unsafe_allow_html=True,
)

if not filtered_articles:
    st.info(
        "No related news articles were found for this category. "
        "Try refreshing the feed."
    )
else:
    for start in range(0, min(len(filtered_articles), 12), 2):
        row_articles = filtered_articles[start:start + 2]
        columns = st.columns(2, gap="medium")

        for column, article in zip(columns, row_articles):
            with column:
                article_card(article, start)


# Show selected event details in a centered dialog.
selected_event = st.session_state.get("selected_event")

if selected_event:
    show_disaster_dialog(selected_event)


st.divider()

st.markdown(
    """
    <div style="
        color:#9ca3af;
        font-size:12px;
        line-height:1.7;
    ">
        <b>Data sources:</b> USGS Earthquake Hazards Program,
        GDACS, and Google News RSS.<br>
        This dashboard aggregates public reports and news.
        News reports are not necessarily official confirmations.
        Missing values are shown as unknown rather than estimated.<br>
        All displayed timestamps use UTC.
    </div>
    """,
    unsafe_allow_html=True,
)
