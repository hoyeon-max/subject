
import html
import re
from urllib.parse import urljoin
from html.parser import HTMLParser

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

# =========================================================
# 1. 페이지 설정
# =========================================================
st.set_page_config(
    page_title="AUTOLAB | 자동차 조회 & 튜닝",
    page_icon="🚘",
    layout="wide",
)

# =========================================================
# 2. CSS
# =========================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', sans-serif;
}
.stApp {
    background: #f4f6f9;
    color: #202938;
}
.block-container {
    max-width: 1450px;
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}
.hero {
    padding: 34px;
    border-radius: 22px;
    color: white;
    background: linear-gradient(120deg, #15243b, #31577c);
    margin-bottom: 24px;
}
.hero h1 {
    color: white;
    font-size: 34px;
    font-weight: 800;
    margin-bottom: 10px;
}
.hero p {
    color: #dbe7f5;
    line-height: 1.8;
    margin-bottom: 0;
}
.section-title {
    font-size: 23px;
    font-weight: 800;
    margin: 20px 0 12px;
}
.vehicle-card {
    background: white;
    border: 1px solid #e3e8ef;
    border-radius: 17px;
    padding: 20px;
}
.vehicle-name {
    font-size: 25px;
    font-weight: 800;
    margin: 6px 0;
}
.vehicle-meta {
    color: #65748a;
    font-size: 13px;
}
.price {
    color: #1765c0;
    font-size: 24px;
    font-weight: 800;
    margin: 14px 0;
}
.unknown-price {
    color: #b45309;
    font-weight: 800;
    font-size: 19px;
    margin: 14px 0;
}
.notice {
    background: #fff7e6;
    color: #92400e;
    border: 1px solid #fde2a7;
    border-radius: 12px;
    padding: 14px 17px;
    line-height: 1.7;
    margin: 12px 0;
}
div[data-testid="stMetric"] {
    background: white;
    border: 1px solid #e5e9f0;
    border-radius: 14px;
    padding: 14px;
}
div.stButton > button {
    border-radius: 10px;
    font-weight: 700;
    min-height: 42px;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# 3. 공식 사이트 및 차량 데이터
#
# 가격은 원 단위. 검증하지 못한 가격은 None으로 둡니다.
# 공식 가격은 연식, 트림, 세금, 판매 조건에 따라 달라집니다.
# =========================================================
URLS = {
    "현대": "https://www.hyundai.com/kr/ko/e/all-vehicles",
    "기아": "https://www.kia.com/kr/vehicles",
    "제네시스": "https://www.genesis.com/kr/ko/",
    "KGM": "https://www.kg-mobility.com/",
    "르노코리아": "https://www.renault.co.kr/",
    "쉐보레": "https://www.chevrolet.co.kr/",
    "BMW": "https://www.bmw.co.kr/",
    "메르세데스-벤츠": "https://www.mercedes-benz.co.kr/",
    "아우디": "https://www.audi.co.kr/",
    "테슬라": "https://www.tesla.com/ko_kr",
    "토요타": "https://www.toyota.co.kr/",
    "렉서스": "https://www.lexus.co.kr/",
    "볼보": "https://www.volvocars.com/kr/",
    "포르쉐": "https://www.porsche.com/korea/ko/",
    "BYD": "https://www.bydauto.kr/",
}

# 데이터 형식: 브랜드, 모델, 차체, 연료, 기본 가격
RAW_CARS = [
    ("현대","아반떼","세단","가솔린",None),
    ("현대","아반떼 하이브리드","세단","하이브리드",None),
    ("현대","쏘나타 디 엣지","세단","가솔린",None),
    ("현대","쏘나타 하이브리드","세단","하이브리드",None),
    ("현대","그랜저","세단","가솔린",None),
    ("현대","그랜저 하이브리드","세단","하이브리드",None),
    ("현대","베뉴","SUV","가솔린",None),
    ("현대","코나","SUV","가솔린",None),
    ("현대","코나 하이브리드","SUV","하이브리드",None),
    ("현대","투싼","SUV","가솔린",None),
    ("현대","싼타페","SUV","가솔린",None),
    ("현대","팰리세이드","SUV","가솔린",None),
    ("현대","아이오닉 5","SUV","전기",None),
    ("현대","아이오닉 6","세단","전기",None),
    ("현대","아이오닉 9","SUV","전기",None),
    ("현대","아반떼 N","세단","가솔린",None),

    ("기아","모닝","경차","가솔린",None),
    ("기아","레이","경차","가솔린",None),
    ("기아","K5","세단","가솔린",None),
    ("기아","K8","세단","가솔린",None),
    ("기아","K9","세단","가솔린",None),
    ("기아","셀토스","SUV","가솔린",None),
    ("기아","스포티지","SUV","가솔린",None),
    ("기아","쏘렌토","SUV","가솔린",None),
    ("기아","카니발","MPV","가솔린",None),
    ("기아","EV3","SUV","전기",None),
    ("기아","EV6","SUV","전기",None),
    ("기아","EV9","SUV","전기",None),

    ("제네시스","G70","세단","가솔린",None),
    ("제네시스","G80","세단","가솔린",None),
    ("제네시스","G90","세단","가솔린",None),
    ("제네시스","GV60","SUV","전기",None),
    ("제네시스","GV70","SUV","가솔린",None),
    ("제네시스","GV80","SUV","가솔린",None),

    ("KGM","티볼리","SUV","가솔린",None),
    ("KGM","토레스","SUV","가솔린",None),
    ("KGM","렉스턴","SUV","가솔린",None),
    ("르노코리아","아르카나","SUV","하이브리드",None),
    ("르노코리아","그랑 콜레오스","SUV","하이브리드",None),
    ("쉐보레","트랙스 크로스오버","SUV","가솔린",None),
    ("쉐보레","트레일블레이저","SUV","가솔린",None),

    ("BMW","1시리즈","해치백","가솔린",None),
    ("BMW","3시리즈","세단","가솔린",None),
    ("BMW","5시리즈","세단","가솔린",None),
    ("BMW","7시리즈","세단","가솔린",None),
    ("BMW","X1","SUV","가솔린",None),
    ("BMW","X3","SUV","가솔린",None),
    ("BMW","X5","SUV","가솔린",None),
    ("BMW","i4","세단","전기",None),
    ("BMW","i5","세단","전기",None),

    ("메르세데스-벤츠","A-Class","해치백","가솔린",None),
    ("메르세데스-벤츠","C-Class","세단","가솔린",None),
    ("메르세데스-벤츠","E-Class","세단","가솔린",None),
    ("메르세데스-벤츠","S-Class","세단","가솔린",None),
    ("메르세데스-벤츠","GLA","SUV","가솔린",None),
    ("메르세데스-벤츠","GLC","SUV","가솔린",None),
    ("메르세데스-벤츠","GLE","SUV","가솔린",None),
    ("메르세데스-벤츠","EQS","세단","전기",None),

    ("아우디","A3","세단","가솔린",None),
    ("아우디","A5","세단","가솔린",None),
    ("아우디","A6","세단","가솔린",None),
    ("아우디","Q5","SUV","가솔린",None),
    ("아우디","Q8 e-tron","SUV","전기",None),

    ("테슬라","Model 3","세단","전기",None),
    ("테슬라","Model Y","SUV","전기",None),
    ("테슬라","Model S","세단","전기",None),
    ("테슬라","Model X","SUV","전기",None),

    ("토요타","캠리","세단","하이브리드",None),
    ("토요타","프리우스","해치백","하이브리드",None),
    ("토요타","RAV4","SUV","하이브리드",None),

    ("렉서스","ES","세단","하이브리드",None),
    ("렉서스","NX","SUV","하이브리드",None),
    ("렉서스","RX","SUV","하이브리드",None),

    ("볼보","EX30","SUV","전기",None),
    ("볼보","XC60","SUV","하이브리드",None),
    ("볼보","XC90","SUV","하이브리드",None),

    ("포르쉐","718 카이맨","쿠페","가솔린",None),
    ("포르쉐","911","쿠페","가솔린",None),
    ("포르쉐","타이칸","세단","전기",None),
    ("포르쉐","마칸","SUV","가솔린",None),
    ("포르쉐","카이엔","SUV","가솔린",None),

    ("BYD","돌핀","해치백","전기",None),
    ("BYD","아토 3","SUV","전기",None),
    ("BYD","씰","세단","전기",None),
    ("BYD","씨라이언 7","SUV","전기",None),
]

CARS = [
    {
        "brand": brand,
        "model": model,
        "body": body,
        "fuel": fuel,
        "price": price,
        "url": URLS[brand],
    }
    for brand, model, body, fuel, price in RAW_CARS
]

# =========================================================
# 4. 공식 웹페이지 이미지 추출기
# =========================================================
class PageImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.og_image = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)

        if tag == "meta":
            if a.get("property") == "og:image":
                self.og_image = a.get("content")
            if a.get("name") == "twitter:image" and not self.og_image:
                self.og_image = a.get("content")

        if tag == "img":
            src = (
                a.get("src")
                or a.get("data-src")
                or a.get("data-original")
                or a.get("data-lazy-src")
            )
            if src:
                self.images.append({
                    "src": src,
                    "alt": a.get("alt", ""),
                    "title": a.get("title", ""),
                })

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def normalize_text(text):
    return re.sub(r"[^a-zA-Z0-9가-힣]", "", str(text)).lower()


def is_image_url(url):
    low = url.lower().split("?")[0]
    return (
        low.endswith((".jpg", ".jpeg", ".png", ".webp", ".avif"))
        or "/image/" in low
        or "image" in low
        or "media" in low
    )


def angle_score(item, model):
    """
    이미지의 alt/title/URL에 모델명과 각도 단서가 있는지 평가합니다.
    단서가 없으면 해당 이미지를 각도별 사진이라고 추정하지 않습니다.
    """
    text = " ".join([
        item.get("alt", ""),
        item.get("title", ""),
        item.get("src", ""),
    ]).lower()

    compact = normalize_text(text)
    model_compact = normalize_text(model)

    # 모델명이 이미지 설명이나 주소에 있는 사진을 우선합니다.
    if model_compact not in compact:
        return None

    front_words = [
        "front", "frontview", "frontthreequarter",
        "front3quarter", "threequarter", "3quarter",
        "3 4 view", "정면", "전면", "대각선", "사선",
    ]
    side_words = [
        "side", "sideview", "profile", "lateral",
        "측면", "옆면", "옆모습",
    ]

    front_hit = any(word in text for word in front_words)
    side_hit = any(word in text for word in side_words)

    # URL 또는 alt에 구체적인 각도 단서가 있어야 인정합니다.
    if front_hit and not side_hit:
        return "front"
    if side_hit and not front_hit:
        return "side"

    return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_angle_images(page_url, model):
    """
    제조사 공식 모델 페이지에서 측면/대각선 정면 이미지를 찾습니다.

    주의:
    많은 제조사 사이트는 JavaScript로 이미지를 불러오기 때문에
    이 방식으로 모든 모델의 이미지가 발견되는 것은 아닙니다.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(
            page_url,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()

        if "html" not in response.headers.get("Content-Type", "").lower():
            return {"side": None, "front": None}

        parser = PageImageParser()
        parser.feed(response.text)

        side_candidates = []
        front_candidates = []

        for item in parser.images:
            absolute_url = urljoin(page_url, item["src"])

            if not absolute_url.startswith(("http://", "https://")):
                continue

            item["src"] = absolute_url
            score = angle_score(item, model)

            if score == "side":
                side_candidates.append(absolute_url)
            elif score == "front":
                front_candidates.append(absolute_url)

        # 실제로 각도가 확인된 이미지에 한해서 반환
        return {
            "side": side_candidates[0] if side_candidates else None,
            "front": front_candidates[0] if front_candidates else None,
        }

    except Exception:
        return {"side": None, "front": None}


# =========================================================
# 5. 유틸리티
# =========================================================
def won(value):
    if value is None or pd.isna(value):
        return "가격 확인 필요"
    return f"{int(value):,}원"


def price_range(value):
    if value is None or pd.isna(value):
        return "가격 미확인"
    value = int(value)
    if value < 30_000_000:
        return "3,000만원 미만"
    if value < 50_000_000:
        return "3,000만~5,000만원"
    if value < 80_000_000:
        return "5,000만~8,000만원"
    if value < 120_000_000:
        return "8,000만~1억 2,000만원"
    return "1억 2,000만원 이상"


def short_won(value):
    if value is None or pd.isna(value):
        return "미확인"
    return f"{int(value):,}원"


# =========================================================
# 6. 마우스 오버 이미지 뷰어
# =========================================================
def show_car_angle_view(side_url, front_url, height=390):
    """
    side_url: 차량 측면 사진
    front_url: 대각선 앞쪽 3/4 사진

    두 이미지가 모두 있을 때 hover 전환합니다.
    정면 사진이 없으면 측면 사진만 표시합니다.
    """
    if not side_url:
        st.markdown("""
        <div style="
            background:#eaf0f7;border-radius:16px;padding:55px 20px;
            text-align:center;color:#52647a;">
            <div style="font-size:60px;">🚘</div>
            <b>공식 측면 이미지 확인 필요</b>
            <p style="font-size:13px;">
                제조사 페이지의 이미지가 자동 수집되지 않았습니다.
            </p>
        </div>
        """, unsafe_allow_html=True)
        return

    if not front_url:
        st.image(side_url, use_container_width=True)
        st.caption(
            "측면 이미지를 표시 중입니다. "
            "대각선 정면 사진은 공식 출처에서 확인되지 않았습니다."
        )
        return

    side = html.escape(side_url, quote=True)
    front = html.escape(front_url, quote=True)

    components.html(
        f"""
        <div class="car-angle-view">
            <img class="car-side"
                 src="{side}"
                 alt="자동차 측면 사진">
            <img class="car-front"
                 src="{front}"
                 alt="자동차 대각선 정면 사진">
            <div class="angle-hint">
                ↗ 마우스를 올려 대각선 정면 보기
            </div>
        </div>

        <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            margin: 0;
            padding: 0;
            background: transparent;
        }}
        .car-angle-view {{
            position: relative;
            width: 100%;
            height: {int(height)}px;
            overflow: hidden;
            border-radius: 16px;
            background: linear-gradient(135deg,#eef2f6,#ffffff);
            cursor: pointer;
        }}
        .car-angle-view img {{
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            object-fit: contain;
            transition:
                opacity .45s ease,
                transform .55s ease;
        }}
        .car-side {{
            opacity: 1;
            transform: scale(1);
        }}
        .car-front {{
            opacity: 0;
            transform: scale(.96) rotateY(-8deg);
        }}
        .car-angle-view:hover .car-side {{
            opacity: 0;
            transform: scale(.96) rotateY(8deg);
        }}
        .car-angle-view:hover .car-front {{
            opacity: 1;
            transform: scale(1) rotateY(0deg);
        }}
        .angle-hint {{
            position: absolute;
            right: 12px;
            bottom: 12px;
            z-index: 5;
            padding: 8px 12px;
            color: #fff;
            background: rgba(20,35,55,.82);
            border-radius: 20px;
            font-size: 12px;
            pointer-events: none;
        }}
        @media (prefers-reduced-motion: reduce) {{
            .car-angle-view img {{
                transition: none;
            }}
        }}
        </style>
        """,
        height=height + 10,
        scrolling=False,
    )


# =========================================================
# 7. 헤더
# =========================================================
st.markdown("""
<div class="hero">
    <h1>🚘 AUTOLAB</h1>
    <p>
        국내외 차량을 조회하고 나만의 튜닝 예산을 구성하세요.<br>
        차량 이미지에 마우스를 올리면 측면에서 대각선 정면으로 전환됩니다.
    </p>
</div>
""", unsafe_allow_html=True)

# =========================================================
# 8. 검색 필터
# =========================================================
df = pd.DataFrame(CARS)

with st.sidebar:
    st.title("🔎 자동차 찾기")

    brands = ["전체"] + sorted(df["brand"].unique().tolist())
    brand = st.selectbox("브랜드", brands)

    bodies = ["전체"] + sorted(df["body"].unique().tolist())
    body = st.selectbox("차종 / 차체", bodies)

    fuels = ["전체"] + sorted(df["fuel"].unique().tolist())
    fuel = st.selectbox("연료", fuels)

    price_options = [
        "전체",
        "3,000만원 미만",
        "3,000만~5,000만원",
        "5,000만~8,000만원",
        "8,000만~1억 2,000만원",
        "1억 2,000만원 이상",
        "가격 미확인",
    ]
    selected_price = st.selectbox("기본 가격대", price_options)

    search_text = st.text_input("차량명 검색", placeholder="예: 아반떼, Model Y")
    show_unknown = st.checkbox("가격 미확인 차량 포함", value=True)

filtered = df.copy()

if brand != "전체":
    filtered = filtered[filtered["brand"] == brand]
if body != "전체":
    filtered = filtered[filtered["body"] == body]
if fuel != "전체":
    filtered = filtered[filtered["fuel"] == fuel]
if search_text.strip():
    query = search_text.strip().lower()
    filtered = filtered[
        filtered["model"].str.lower().str.contains(query, regex=False)
        | filtered["brand"].str.lower().str.contains(query, regex=False)
    ]

if selected_price != "전체":
    filtered = filtered[
        filtered["price"].apply(price_range) == selected_price
    ]

if not show_unknown and selected_price != "가격 미확인":
    filtered = filtered[filtered["price"].notna()]

# =========================================================
# 9. 차량 선택 및 상세 정보
# =========================================================
st.markdown(
    '<div class="section-title">🚗 차량 조회</div>',
    unsafe_allow_html=True,
)
st.caption(f"검색 결과: {len(filtered)}대")

if filtered.empty:
    st.warning("조건에 맞는 차량이 없습니다. 필터를 변경해 주세요.")
    st.stop()

labels = [
    f"{row['brand']} · {row['model']}"
    for _, row in filtered.iterrows()
]

selected_label = st.selectbox(
    "상세 정보를 확인할 차량",
    labels,
    key="vehicle_select",
)
selected_idx = labels.index(selected_label)
car = filtered.iloc[selected_idx].to_dict()

col_info, col_image = st.columns([0.9, 1.1], gap="large")

with col_info:
    st.markdown('<div class="vehicle-card">', unsafe_allow_html=True)
    st.markdown(
        f"<div class='vehicle-meta'>"
        f"{html.escape(car['brand'])} · "
        f"{html.escape(car['body'])} · "
        f"{html.escape(car['fuel'])}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='vehicle-name'>{html.escape(car['model'])}</div>",
        unsafe_allow_html=True,
    )

    if car["price"] is None or pd.isna(car["price"]):
        st.markdown(
            "<div class='unknown-price'>공식 기본 가격 확인 필요</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div class='price'>{won(car['price'])}부터</div>",
            unsafe_allow_html=True,
        )

    st.write("**옵션:** 가격 계산에서 제외")
    st.write("**가격 기준:** 제조사 공식 가격표 확인 필요")
    st.markdown("</div>", unsafe_allow_html=True)

    st.link_button(
        "🏢 제조사 공식 사이트 열기",
        car["url"],
        use_container_width=True,
    )

with col_image:
    st.markdown("#### 🖼️ 차량 이미지")
    st.caption("측면 → 대각선 정면 · 이미지 위에 마우스를 올려 보세요.")

    with st.spinner("공식 사이트에서 각도별 이미지 검색 중..."):
        angle_images = fetch_angle_images(car["url"], car["model"])

    show_car_angle_view(
        side_url=angle_images["side"],
        front_url=angle_images["front"],
    )

    if not angle_images["side"]:
        st.caption(
            "자동 이미지 수집은 제조사 페이지 구조에 따라 실패할 수 있습니다. "
            "공식 사이트 링크에서 해당 차량의 사진을 확인하세요."
        )

# =========================================================
# 10. 튜닝 항목과 예산
# =========================================================
st.divider()
st.markdown(
    '<div class="section-title">🛠️ 튜닝 구성</div>',
    unsafe_allow_html=True,
)

st.markdown("""
<div class="notice">
    아래 금액은 예산 계획용 예시이며 업체의 공식 견적이 아닙니다.
    실제 가격은 차종, 부품, 공임 및 장착 조건에 따라 달라집니다.
</div>
""", unsafe_allow_html=True)

TUNING = {
    "외관": {
        "description": "바디킷, 스포일러, 랩핑 등",
        "default": 1_000_000,
    },
    "휠·타이어": {
        "description": "휠과 타이어 교체 예산",
        "default": 1_500_000,
    },
    "서스펜션": {
        "description": "서스펜션 및 차고 조절 관련 부품",
        "default": 1_200_000,
    },
    "실내": {
        "description": "실내 트림, 매트, 장식 등",
        "default": 500_000,
    },
}

chosen_tuning = st.multiselect(
    "원하는 튜닝 항목",
    list(TUNING.keys()),
    default=[],
)

tuning_costs = {}
if chosen_tuning:
    cols = st.columns(2)
    for i, item in enumerate(chosen_tuning):
        with cols[i % 2]:
            tuning_costs[item] = st.number_input(
                f"{item} 예상 비용 (원)",
                min_value=0,
                max_value=100_000_000,
                value=TUNING[item]["default"],
                step=100_000,
                key=f"cost_{item}",
                help=TUNING[item]["description"],
            )
            st.caption(TUNING[item]["description"])

tuning_total = sum(tuning_costs.values())
base_price = car["price"]

st.markdown("#### 🧾 예상 비용 요약")
m1, m2, m3 = st.columns(3)

with m1:
    st.metric("차량 기본 가격", short_won(base_price))
with m2:
    st.metric("튜닝 비용", won(tuning_total))
with m3:
    if base_price is not None and not pd.isna(base_price):
        st.metric("차량 + 튜닝 합계", won(int(base_price) + tuning_total))
    else:
        st.metric("차량 + 튜닝 합계", "차량 가격 확인 필요")

if chosen_tuning:
    breakdown = pd.DataFrame([
        {
            "튜닝 항목": item,
            "내용": TUNING[item]["description"],
            "예상 비용": tuning_costs[item],
        }
        for item in chosen_tuning
    ])

    st.dataframe(
        breakdown,
        use_container_width=True,
        hide_index=True,
        column_config={
            "예상 비용": st.column_config.NumberColumn(
                "예상 비용",
                format="%d원",
            )
        },
    )
else:
    st.info("튜닝 항목을 선택하면 비용이 자동으로 계산됩니다.")

# =========================================================
# 11. 선택 구성 미리보기
# =========================================================
st.divider()
st.markdown(
    '<div class="section-title">🎨 나의 튜닝 구성 미리보기</div>',
    unsafe_allow_html=True,
)

preview_col, summary_col = st.columns([1, 1])

with preview_col:
    if angle_images["side"]:
        st.image(angle_images["side"], use_container_width=True)
    else:
        st.markdown("""
        <div style="
            background:#eaf0f7;border-radius:16px;padding:50px 20px;
            text-align:center;">
            <div style="font-size:60px;">🚙</div>
            <b>차량 이미지 확인 필요</b>
        </div>
        """, unsafe_allow_html=True)

with summary_col:
    st.markdown(f"### {car['brand']} {car['model']}")
    st.write(f"차체: {car['body']} · 연료: {car['fuel']}")

    if chosen_tuning:
        for item in chosen_tuning:
            st.write(f"🔧 **{item}** — {won(tuning_costs[item])}")
    else:
        st.write("선택한 튜닝 항목이 없습니다.")

    st.divider()
    st.write(f"튜닝 예산: **{won(tuning_total)}**")

    if base_price is not None and not pd.isna(base_price):
        st.write(f"예상 총액: **{won(int(base_price) + tuning_total)}**")
    else:
        st.write("예상 총액: **차량 기본 가격 확인 후 계산 가능**")

# =========================================================
# 12. 공식 사이트 링크 및 안내
# =========================================================
st.divider()
st.markdown("### 🔗 제조사 공식 사이트")

link_cols = st.columns(3)
for i, (brand_name, brand_url) in enumerate(URLS.items()):
    with link_cols[i % 3]:
        st.markdown(f"- [{brand_name}]({brand_url})")

st.markdown("""
### 이용 시 주의사항

- 등록된 차종 목록은 앱에서 관리하는 목록이며 제조사의 전체 라인업을 보장하지 않습니다.
- 가격을 확인하지 못한 차량은 임의의 가격을 표시하지 않습니다.
- 공식 사이트가 JavaScript로 이미지를 불러오거나 접근을 제한하면 자동 수집에 실패할 수 있습니다.
- 대각선 정면 사진은 이미지 설명이나 주소에 모델명과 각도 단서가 있는 경우에만 선택합니다. 따라서 사진 두 장을 항상 자동으로 찾을 수 있는 것은 아닙니다.
- 차량 사진 전환은 두 개의 서로 다른 사진 사이의 효과입니다. 한 장의 사진을 3D로 변환하는 기능은 아닙니다.
- 튜닝 전에는 차량 보증, 안전성, 소음·배출가스 기준 및 구조변경 관련 규정을 확인하세요.
""")

st.caption("AUTOLAB · 자동차 조회 & 튜닝 예산 도구")
