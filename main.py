
import html
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components


# =========================================================
# 1. APP CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="WORLD DISASTER LIVE",
    layout="wide",
    initial_sidebar_state="collapsed",
)

logging.basicConfig(level=logging.ERROR)

REQUEST_TIMEOUT = 15

# Main theme colors
BG = "#0f172a"
PANEL = "#172033"
PANEL_HOVER = "#1e293b"
BORDER = "#334155"
TEXT = "#f8fafc"
MUTED = "#94a3b8"
ACCENT = "#38bdf8"

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

HAZARD_LABELS = dict(HAZARDS)

HAZARD_KEYWORDS = {
    "TYPHOON": [
        "typhoon", "hurricane", "cyclone",
        "tropical storm", "tropical cyclone",
    ],
    "EARTHQUAKE": [
        "earthquake", "seismic", "aftershock",
    ],
    "WILDFIRE": [
        "wildfire", "forest fire", "bushfire", "wild fire",
    ],
    "FLOOD": [
        "flood", "flash flood", "flooding", "inundation",
    ],
    "HEAVY_RAIN": [
        "heavy rain", "torrential rain", "downpour",
        "monsoon rain",
    ],
    "DROUGHT": [
        "drought", "water shortage",
    ],
    "HEAVY_SNOW": [
        "heavy snow", "snowstorm", "blizzard", "snowfall",
    ],
    "HEATWAVE": [
        "heatwave", "heat wave", "extreme heat",
    ],
    "COLD_WAVE": [
        "cold wave", "extreme cold", "cold snap",
    ],
    "LANDSLIDE": [
        "landslide", "mudslide", "rockslide",
    ],
}

HAZARD_COLORS = {
    "ALL": "#cbd5e1",
    "TYPHOON": "#c4b5fd",
    "EARTHQUAKE": "#f87171",
    "WILDFIRE": "#fb923c",
    "FLOOD": "#60a5fa",
    "HEAVY_RAIN": "#22d3ee",
    "DROUGHT": "#facc15",
    "HEAVY_SNOW": "#e2e8f0",
    "HEATWAVE": "#fb7185",
    "COLD_WAVE": "#7dd3fc",
    "LANDSLIDE": "#d6a77a",
}


# =========================================================
# 2. GLOBAL CSS
# =========================================================
st.markdown(
    f"""
    <style>
    :root {{
        color-scheme: dark;
        --app-bg: {BG};
        --panel-bg: {PANEL};
        --panel-hover: {PANEL_HOVER};
        --border-color: {BORDER};
        --main-text: {TEXT};
        --muted-text: {MUTED};
        --accent-color: {ACCENT};
    }}

    html,
    body,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stHeader"],
    [data-testid="stToolbar"] {{
        background-color: {BG} !important;
        color: {TEXT} !important;
    }}

    [data-testid="stAppViewContainer"] {{
        background: {BG} !important;
    }}

    [data-testid="stMain"] {{
        background: {BG} !important;
    }}

    [data-testid="stMainBlockContainer"] {{
        max-width: 1600px;
        padding-top: 0.4rem;
        padding-bottom: 2.5rem;
    }}

    [data-testid="stHeader"] {{
        background: {BG} !important;
    }}

    [data-testid="stToolbar"] {{
        background: {BG} !important;
    }}

    body,
    p,
    label,
    span,
    div {{
        scrollbar-color: #475569 {BG};
    }}

    .main-title {{
        color: {TEXT};
        text-align: center;
        font-size: clamp(27px, 4vw, 43px);
        font-weight: 900;
        letter-spacing: 1px;
        margin-top: 0.4rem;
        margin-bottom: 0.2rem;
    }}

    .main-subtitle {{
        color: {MUTED};
        text-align: center;
        font-size: 14px;
        margin-bottom: 1.2rem;
    }}

    .menu-heading {{
        width: 100%;
        padding: 10px 0 9px;
        color: {MUTED};
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 1.7px;
    }}

    .section-title {{
        color: {TEXT};
        font-size: 1.2rem;
        font-weight: 800;
        margin: 1rem 0 0.7rem;
    }}

    .event-card {{
        box-sizing: border-box;
        border: 1px solid {BORDER};
        border-radius: 14px;
        padding: 17px;
        min-height: 180px;
        background: {PANEL};
        margin-bottom: 8px;
        overflow-wrap: anywhere;
        transition: border-color 0.15s ease,
                    background 0.15s ease;
    }}

    .event-card:hover {{
        border-color: #64748b;
        background: {PANEL_HOVER};
    }}

    .event-type {{
        font-size: 0.75rem;
        font-weight: 800;
        letter-spacing: 1.1px;
        margin-bottom: 8px;
    }}

    .event-title {{
        color: {TEXT};
        font-size: 1rem;
        font-weight: 750;
        line-height: 1.5;
        margin-bottom: 10px;
    }}

    .event-meta {{
        color: {MUTED};
        font-size: 0.82rem;
        line-height: 1.8;
    }}

    /* All Streamlit buttons */
    div[data-testid="stButton"] > button {{
        width: 100%;
        min-height: 44px;
        border-radius: 9px;
        font-weight: 700;
        border: 1px solid {BORDER};
        transition: background 0.15s ease,
                    border-color 0.15s ease;
    }}

    div[data-testid="stButton"] > button[kind="secondary"] {{
        background: {PANEL} !important;
        color: {TEXT} !important;
        border-color: {BORDER} !important;
    }}

    div[data-testid="stButton"] > button[kind="secondary"]:hover {{
        background: {PANEL_HOVER} !important;
        border-color: #64748b !important;
        color: #ffffff !important;
    }}

    div[data-testid="stButton"] > button[kind="primary"] {{
        background: {ACCENT} !important;
        color: #082f49 !important;
        border-color: {ACCENT} !important;
    }}

    div[data-testid="stButton"] > button[kind="primary"]:hover {{
        background: #7dd3fc !important;
        border-color: #7dd3fc !important;
    }}

    /* Metric panels */
    [data-testid="stMetric"] {{
        background: {PANEL} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 12px !important;
        padding: 13px 16px !important;
    }}

    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] p {{
        color: {MUTED} !important;
    }}

    [data-testid="stMetricValue"] {{
        color: {TEXT} !important;
    }}

    /* News containers and general bordered containers */
    [data-testid="stVerticalBlockBorderWrapper"] > div {{
        background: {PANEL} !important;
        border-color: {BORDER} !important;
        border-radius: 12px !important;
    }}

    /* Links */
    a {{
        color: {ACCENT};
    }}

    div[data-testid="stLinkButton"] > a {{
        background: {PANEL} !important;
        color: {TEXT} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 8px;
    }}

    div[data-testid="stLinkButton"] > a:hover {{
        background: {PANEL_HOVER} !important;
        border-color: #64748b !important;
    }}

    /* Dividers */
    hr {{
        border-color: {BORDER} !important;
    }}

    /* Alerts */
    [data-testid="stAlert"] {{
        background: {PANEL} !important;
        border: 1px solid {BORDER} !important;
        color: {TEXT} !important;
        border-radius: 10px;
    }}

    /* Inputs, select boxes, text areas */
    [data-baseweb="select"] > div,
    [data-baseweb="input"] > div,
    [data-baseweb="textarea"] > div {{
        background: {PANEL} !important;
        border-color: {BORDER} !important;
        color: {TEXT} !important;
    }}

    /* Dialog backdrop and dialog window */
    [data-testid="stDialog"] {{
        background: rgba(2, 6, 23, 0.82) !important;
    }}

    [data-testid="stDialog"] > div {{
        background: {BG} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 16px !important;
    }}

    [data-testid="stDialog"] [data-testid="stVerticalBlock"] {{
        background: transparent;
    }}

    [data-testid="stDialog"] h1,
    [data-testid="stDialog"] h2,
    [data-testid="stDialog"] h3,
    [data-testid="stDialog"] p,
    [data-testid="stDialog"] label {{
        color: {TEXT};
    }}

    [data-testid="stDialog"] [data-testid="stMetric"] {{
        background: {PANEL} !important;
    }}

    /* Footer text */
    .footer-note {{
        color: {MUTED};
        font-size: 12px;
        line-height: 1.8;
    }}

    @media (max-width: 700px) {{
        .main-title {{
            font-size: 27px;
        }}

        .main-subtitle {{
            font-size: 12px;
        }}

        .event-card {{
            min-height: auto;
        }}
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 3. LARGE UTC CLOCK
# =========================================================
def render_utc_header():
    components.html(
        f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            * {{
                box-sizing: border-box;
            }}

            html, body {{
                margin: 0;
                padding: 0;
                width: 100%;
                background: {BG};
                color: {TEXT};
                font-family: Arial, Helvetica, sans-serif;
                overflow: hidden;
            }}

            .header {{
                position: relative;
                width: 100%;
                min-height: 205px;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px 190px 24px;
                background: {BG};
                border-bottom: 1px solid {BORDER};
            }}

            .clock-area {{
                width: 100%;
                text-align: center;
            }}

            #clock {{
                font-size: clamp(76px, 11vw, 132px);
                font-weight: 900;
                line-height: 1.05;
                letter-spacing: 4px;
                color: #ffffff;
                text-shadow: 0 0 22px rgba(56,189,248,0.12);
                font-variant-numeric: tabular-nums;
                white-space: nowrap;
            }}

            .utc {{
                display: inline-block;
                margin-top: 10px;
                padding: 5px 16px;
                border: 1px solid #475569;
                border-radius: 6px;
                color: #cbd5e1;
                background: {PANEL};
                font-size: 15px;
                font-weight: 800;
                letter-spacing: 5px;
            }}

            #date {{
                position: absolute;
                top: 24px;
                right: 20px;
                text-align: right;
                color: #f1f5f9;
                font-size: 16px;
                font-weight: 700;
                line-height: 1.6;
                white-space: nowrap;
            }}

            .date-label {{
                display: block;
                font-size: 11px;
                color: {MUTED};
                letter-spacing: 2px;
                margin-bottom: 3px;
            }}

            @media (max-width: 700px) {{
                .header {{
                    min-height: 170px;
                    padding: 52px 5px 15px;
                }}

                #clock {{
                    font-size: clamp(48px, 12vw, 76px);
                    letter-spacing: 1px;
                }}

                #date {{
                    top: 6px;
                    right: 8px;
                    font-size: 12px;
                }}

                .date-label {{
                    font-size: 9px;
                }}

                .utc {{
                    font-size: 12px;
                    margin-top: 8px;
                }}
            }}
        </style>
        </head>

        <body>
            <div class="header">
                <div class="clock-area">
                    <div id="clock">00:00:00</div>
                    <div class="utc">UTC</div>
                </div>

                <div id="date">
                    <span class="date-label">CURRENT DATE</span>
                    <span id="date-value">0000-00-00</span>
                </div>
            </div>

            <script>
                function updateClock() {{
                    const now = new Date();
                    const pad = n => String(n).padStart(2, "0");

                    document.getElementById("clock").textContent =
                        pad(now.getUTCHours()) + ":" +
                        pad(now.getUTCMinutes()) + ":" +
                        pad(now.getUTCSeconds());

                    document.getElementById("date-value").textContent =
                        now.getUTCFullYear() + "-" +
                        pad(now.getUTCMonth() + 1) + "-" +
                        pad(now.getUTCDate());
                }}

                updateClock();
                setInterval(updateClock, 1000);
            </script>
        </body>
        </html>
        """,
        height=220,
        scrolling=False,
    )


# =========================================================
# 4. FUNCTIONAL HORIZONTAL HAZARD MENU
# =========================================================
def render_hazard_menu():
    st.markdown(
        """
        <div class="menu-heading">SELECT DISASTER TYPE</div>
        """,
        unsafe_allow_html=True,
    )

    selected = st.session_state.get("hazard", "ALL")

    # Wide, horizontal menu: 6 buttons on row 1, 5 on row 2.
    rows = [HAZARDS[:6], HAZARDS[6:]]

    for row in rows:
        columns = st.columns(len(row), gap="small")

        for column, (label, code) in zip(columns, row):
            with column:
                active = selected == code
                button_label = f"● {label}" if active else label

                if st.button(
                    button_label,
                    key=f"hazard_button_{code}",
                    use_container_width=True,
                    type="primary" if active else "secondary",
                ):
                    st.session_state["hazard"] = code
                    st.session_state.pop("selected_event", None)
                    st.rerun()


# =========================================================
# 5. COMMON UTILITIES
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
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

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
        "User-Agent": "WorldDisasterLive/1.0"
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
        logging.error("Request failed: %s", exc)
        return None


def fetch_json(url):
    import json

    content = fetch_text(url)

    if not content:
        return None

    try:
        return json.loads(content)
    except ValueError:
        return None


def clean_html_text(value):
    value = safe_text(value, "")
    value = html.unescape(value)
    value = __import__("re").sub(r"<[^>]+>", " ", value)
    return " ".join(value.split())


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


def get_hazard_label(code):
    return HAZARD_LABELS.get(
        code,
        code.replace("_", " ").title(),
    )


# =========================================================
# 6. USGS EARTHQUAKES
# =========================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_earthquakes():
    payload = fetch_json(USGS_URL)
    events = []

    if not payload:
        return events

    for feature in payload.get("features", []):
        props = feature.get("properties", {}) or {}
        geometry = feature.get("geometry", {}) or {}
        coords = geometry.get("coordinates", [])

        lon = coords[0] if len(coords) > 0 else None
        lat = coords[1] if len(coords) > 1 else None
        depth = coords[2] if len(coords) > 2 else None

        timestamp_ms = props.get("time")
        event_time = None

        if timestamp_ms is not None:
            event_time = datetime.fromtimestamp(
                timestamp_ms / 1000,
                tz=timezone.utc,
            ).isoformat()

        magnitude = props.get("mag")
        location = safe_text(
            props.get("place"),
            "Location unavailable",
        )

        events.append({
            "id": str(
                feature.get("id", props.get("url", location))
            ),
            "title": f"M{magnitude} Earthquake — {location}",
            "hazard": "EARTHQUAKE",
            "location": location,
            "time": event_time,
            "source": "USGS",
            "source_url": props.get("url"),
            "latitude": lat,
            "longitude": lon,
            "magnitude": magnitude,
            "depth_km": depth,
            "felt": props.get("felt"),
            "alert": props.get("alert"),
            "description": safe_text(
                props.get("title"),
                location,
            ),
            "damage": "Not confirmed by this feed",
        })

    events.sort(
        key=lambda event: event.get("time") or "",
        reverse=True,
    )

    return events


# =========================================================
# 7. GDACS RSS EVENTS
# =========================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_gdacs_events():
    xml_content = fetch_text(GDACS_URL)
    events = []

    if not xml_content:
        return events

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return events

    for item in root.findall(".//item"):
        title = clean_html_text(item.findtext("title", ""))
        description = clean_html_text(
            item.findtext("description", "")
        )
        link = safe_text(item.findtext("link"), "")
        pub_date = item.findtext("pubDate", "")

        hazard = classify_hazard(f"{title} {description}")

        if hazard == "ALL":
            continue

        event_time = None

        if pub_date:
            try:
                parsed = parsedate_to_datetime(pub_date)

                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)

                event_time = parsed.astimezone(
                    timezone.utc
                ).isoformat()

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
        key=lambda event: event.get("time") or "",
        reverse=True,
    )

    return events


# =========================================================
# 8. GOOGLE NEWS RSS
# =========================================================
def google_news_query(hazard):
    queries = {
        "ALL": (
            "global natural disaster OR earthquake OR typhoon "
            "OR wildfire OR flood"
        ),
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
    params = {
        "q": google_news_query(hazard),
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }

    xml_content = fetch_text(
        GOOGLE_NEWS_URL,
        params=params,
    )

    articles = []

    if not xml_content:
        return articles

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return articles

    for item in root.findall(".//item"):
        title = clean_html_text(item.findtext("title", ""))
        description = clean_html_text(
            item.findtext("description", "")
        )
        link = safe_text(item.findtext("link"), "")
        pub_date = item.findtext("pubDate", "")

        source_node = item.find("source")

        if source_node is not None and source_node.text:
            source_name = clean_html_text(source_node.text)
        else:
            source_name = "Google News"

        event_time = None

        if pub_date:
            try:
                parsed = parsedate_to_datetime(pub_date)

                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)

                event_time = parsed.astimezone(
                    timezone.utc
                ).isoformat()

            except (TypeError, ValueError, OverflowError):
                event_time = None

        classified = classify_hazard(
            f"{title} {description}"
        )

        articles.append({
            "title": title or "Untitled report",
            "description": description,
            "url": link,
            "source": source_name,
            "time": event_time,
            "hazard": classified,
        })

    unique_articles = {}

    for article in articles:
        key = article["url"] or article["title"]
        unique_articles[key] = article

    articles = list(unique_articles.values())

    articles.sort(
        key=lambda article: article.get("time") or "",
        reverse=True,
    )

    return articles[:40]


# =========================================================
# 9. FILTERING
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
        combined = (
            str(article.get("title", "")) + " " +
            str(article.get("description", ""))
        ).lower()

        if (
            article.get("hazard") == selected_hazard
            or any(word.lower() in combined for word in keywords)
        ):
            filtered.append(article)

    return filtered


# =========================================================
# 10. EVENT CARDS
# =========================================================
def event_card(event, index):
    hazard = event.get("hazard", "ALL")
    color = HAZARD_COLORS.get(hazard, "#cbd5e1")

    title = html.escape(
        safe_text(event.get("title"), "Untitled event")
    )
    location = html.escape(
        safe_text(event.get("location"), "Unknown")
    )
    source = html.escape(
        safe_text(event.get("source"), "Unknown")
    )
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
        key=f"details_{index}",
        use_container_width=True,
    ):
        st.session_state["selected_event"] = event
        st.rerun()


# =========================================================
# 11. NEWS CARDS
# =========================================================
def article_card(article, index):
    title = safe_text(
        article.get("title"),
        "Untitled report",
    )
    source = safe_text(
        article.get("source"),
        "News source",
    )

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
# 12. DISASTER DETAIL DIALOG
# =========================================================
@st.dialog("Disaster Details", width="large")
def show_disaster_dialog(event):
    hazard = event.get("hazard", "ALL")
    color = HAZARD_COLORS.get(hazard, "#cbd5e1")

    st.markdown(
        f"""
        <div style="
            color:{color};
            font-size:12px;
            font-weight:800;
            letter-spacing:1.5px;
        ">
            {html.escape(get_hazard_label(hazard).upper())}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader(
        safe_text(event.get("title"), "Untitled event")
    )

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
        st.write(safe_text(event.get("alert"), "Unknown"))

    if hazard == "EARTHQUAKE":
        st.markdown("### Earthquake Measurements")

        m1, m2, m3 = st.columns(3)

        magnitude = event.get("magnitude")
        depth = event.get("depth_km")
        felt = event.get("felt")

        m1.metric(
            "Magnitude",
            str(magnitude) if magnitude is not None else "Unknown",
        )

        m2.metric(
            "Depth",
            f"{depth} km" if depth is not None else "Unknown",
        )

        m3.metric(
            "Felt reports",
            str(felt) if felt is not None else "Unknown",
        )

    st.markdown("### Damage and Impact")

    st.info(
        "Verified casualty and damage totals are not available "
        "from this report. Check the original source for confirmed "
        "figures."
    )

    st.write("**Confirmed casualties:** Unknown")
    st.write("**Economic losses:** Unknown")
    st.write("**Damage status:** Not confirmed by this dashboard")

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

    st.markdown("### Original Source")

    if event.get("source_url"):
        st.link_button(
            "Open Original Source",
            event["source_url"],
            use_container_width=True,
        )
    else:
        st.write("Original source link is unavailable.")

    st.caption(
        "All times are UTC. Information may change as agencies "
        "publish updated reports."
    )


# =========================================================
# 13. MAIN APP
# =========================================================
if "hazard" not in st.session_state:
    st.session_state["hazard"] = "ALL"

# Top clock and date
render_utc_header()

# Main title
st.markdown(
    """
    <div class="main-title">WORLD DISASTER LIVE</div>
    <div class="main-subtitle">
        Global Natural Disaster Monitoring Dashboard
    </div>
    """,
    unsafe_allow_html=True,
)

# Functional disaster menu
render_hazard_menu()

selected_hazard = st.session_state["hazard"]

st.divider()

title_col, refresh_col = st.columns([4, 1])

with title_col:
    if selected_hazard == "ALL":
        st.subheader("Latest Global Disaster Reports")
    else:
        st.subheader(
            f"{get_hazard_label(selected_hazard)} Reports"
        )

with refresh_col:
    if st.button(
        "Refresh Data",
        use_container_width=True,
    ):
        load_earthquakes.clear()
        load_gdacs_events.clear()
        load_news.clear()
        st.session_state.pop("selected_event", None)
        st.rerun()


# Fetch live data
with st.spinner("Loading disaster reports..."):
    earthquake_events = load_earthquakes()
    gdacs_events = load_gdacs_events()

    combined_events = earthquake_events + gdacs_events

    # Remove duplicate events
    deduplicated_events = {}

    for event in combined_events:
        event_key = event.get("id") or event.get("title", "")
        deduplicated_events[event_key] = event

    combined_events = list(deduplicated_events.values())

    combined_events.sort(
        key=lambda event: event.get("time") or "",
        reverse=True,
    )

    visible_events = filter_events(
        combined_events,
        selected_hazard,
    )

    news_articles = load_news(selected_hazard)

    visible_articles = filter_articles(
        news_articles,
        selected_hazard,
    )


# Summary metrics
event_count = len(visible_events)
article_count = len(visible_articles)

earthquake_count = sum(
    1 for event in visible_events
    if event.get("hazard") == "EARTHQUAKE"
)

metric1, metric2, metric3 = st.columns(3)

metric1.metric("Disaster Reports", event_count)
metric2.metric("Related News Articles", article_count)
metric3.metric("Earthquake Reports", earthquake_count)


# Live event cards
st.markdown(
    '<div class="section-title">Live Events</div>',
    unsafe_allow_html=True,
)

if not visible_events:
    st.info(
        f"No matching {get_hazard_label(selected_hazard)} events "
        "were found in the available feeds. Try Refresh Data or "
        "select another category."
    )
else:
    displayed_events = visible_events[:30]

    for start in range(0, len(displayed_events), 3):
        event_group = displayed_events[start:start + 3]
        columns = st.columns(3, gap="medium")

        for offset, (column, event) in enumerate(
            zip(columns, event_group)
        ):
            with column:
                event_card(event, start + offset)


# Related news
st.divider()

st.markdown(
    '<div class="section-title">Related News</div>',
    unsafe_allow_html=True,
)

if not visible_articles:
    st.info(
        "No related news articles were found for this category. "
        "Try refreshing the data."
    )
else:
    displayed_articles = visible_articles[:12]

    for start in range(0, len(displayed_articles), 2):
        article_group = displayed_articles[start:start + 2]
        columns = st.columns(2, gap="medium")

        for column, article in zip(columns, article_group):
            with column:
                article_card(article, start)


# Detail dialog
selected_event = st.session_state.get("selected_event")

if selected_event:
    show_disaster_dialog(selected_event)


# Footer
st.divider()

st.markdown(
    f"""
    <div class="footer-note">
        <b>Data Sources:</b> USGS Earthquake Hazards Program,
        GDACS, Google News RSS.<br>
        This dashboard aggregates public reports and news.
        News reports are not necessarily official confirmations.
        Missing damage figures are shown as unknown rather than estimated.<br>
        All timestamps use Coordinated Universal Time (UTC).
        <br><br>
        <span style="color:#64748b;">WORLD DISASTER LIVE</span>
    </div>
    """,
    unsafe_allow_html=True,
)
