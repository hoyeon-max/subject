
import re
import json
import html
from datetime import datetime
from html.parser import HTMLParser

import requests
import streamlit as st
import pandas as pd

# =========================================================
# 1. 페이지 설정
# =========================================================
st.set_page_config(
    page_title="오토랩 | 자동차 조회 & 튜닝",
    page_icon="🚘",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# 2. 디자인
# =========================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', sans-serif;
}
.stApp {
    background: #f5f6f8;
    color: #202733;
}
.block-container {
    padding-top: 1.8rem;
    padding-bottom: 3rem;
    max-width: 1450px;
}
.hero {
    background: linear-gradient(120deg, #15243b, #304c70);
    color: white;
    padding: 34px;
    border-radius: 22px;
    margin-bottom: 22px;
}
.hero h1 {
    color: white;
    font-size: 35px;
    font-weight: 800;
    margin: 0 0 12px 0;
}
.hero p {
    color: #dce7f4;
    font-size: 15px;
    margin: 0;
}
.section-title {
    font-size: 23px;
    font-weight: 800;
    margin: 15px 0;
}
.vehicle-card {
    background: white;
    border: 1px solid #e3e7ed;
    border-radius: 17px;
    padding: 19px;
    margin-bottom: 10px;
}
.vehicle-name {
    font-size: 22px;
    font-weight: 800;
    margin: 7px 0;
}
.vehicle-meta {
    color: #64748b;
    font-size: 13px;
}
.price {
    font-size: 23px;
    font-weight: 800;
    color: #1765c0;
    margin: 10px 0;
}
.unknown-price {
    font-size: 18px;
    color: #b45309;
    font-weight: 800;
    margin: 10px 0;
}
.preview {
    border-radius: 16px;
    padding: 20px;
    background: linear-gradient(135deg, #eaf0f7, #ffffff);
    border: 1px solid #d9e2ed;
}
.preview-title {
    font-size: 19px;
    font-weight: 800;
    color: #243b55;
}
.preview-tag {
    display: inline-block;
    background: #dbeafe;
    color: #1d4ed8;
    padding: 6px 10px;
    border-radius: 18px;
    margin: 4px 3px;
    font-size: 12px;
    font-weight: 700;
}
.notice {
    background: #fff7e6;
    color: #92400e;
    padding: 13px 16px;
    border-radius: 12px;
    border: 1px solid #fde2a7;
    margin: 10px 0;
    font-size: 13px;
}
div[data-testid="stMetric"] {
    background: white;
    border: 1px solid #e5e9f0;
    border-radius: 14px;
    padding: 15px;
}
div.stButton > button {
    border-radius: 10px;
    font-weight: 700;
    min-height: 42px;
}
a {
    text-decoration: none;
}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# =========================================================
# 3. 자동차 데이터
#
# price: 공식 사이트에서 확인한 기본 시작 가격(원)
# None: 현재 코드에 확인 가능한 가격을 넣지 않음
#
# 시작 가격은 세부 트림, 연식, 세제 조건에 따라 달라질 수
# 있으므로 실제 구매 전 공식 가격표를 확인해야 합니다.
# =========================================================

HYUNDAI_URL = "https://www.hyundai.com/kr/ko/e/menu-list"
GENESIS_URL = (
    "https://www.genesis.com/kr/ko/support/"
    "download-center/genesis-models.html"
)
KIA_URL = "https://www.kia.com/kr/vehicles"
KG_M_URL = "https://www.kg-mobility.com/"
RENAULT_URL = "https://www.renault.co.kr/"
CHEVROLET_URL = "https://www.chevrolet.co.kr/"
BMW_URL = "https://www.bmw.co.kr/"
BENZ_URL = "https://www.mercedes-benz.co.kr/"
AUDI_URL = "https://www.audi.co.kr/"
TESLA_URL = "https://www.tesla.com/ko_kr"
TOYOTA_URL = "https://www.toyota.co.kr/"
LEXUS_URL = "https://www.lexus.co.kr/"
VOLVO_URL = "https://www.volvocars.com/kr/"
PORSCHE_URL = "https://www.porsche.com/korea/ko/"
BYD_URL = "https://www.bydauto.kr/"

CARS = [
    # 현대 - 공식 사이트에 표시된 시작 가격
    {"brand":"현대","model":"아반떼","body":"세단","fuel":"가솔린",
     "price":23980000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"아반떼 하이브리드","body":"세단","fuel":"하이브리드",
     "price":30420000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"쏘나타 디 엣지","body":"세단","fuel":"가솔린",
     "price":28660000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"쏘나타 하이브리드","body":"세단","fuel":"하이브리드",
     "price":33180000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"그랜저","body":"세단","fuel":"가솔린",
     "price":42450000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"그랜저 하이브리드","body":"세단","fuel":"하이브리드",
     "price":48330000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"베뉴","body":"SUV","fuel":"가솔린",
     "price":19940000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"코나","body":"SUV","fuel":"가솔린",
     "price":23930000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"코나 하이브리드","body":"SUV","fuel":"하이브리드",
     "price":29380000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"투싼","body":"SUV","fuel":"가솔린",
     "price":28440000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"싼타페","body":"SUV","fuel":"가솔린",
     "price":36570000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"싼타페 하이브리드","body":"SUV","fuel":"하이브리드",
     "price":40220000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"팰리세이드","body":"SUV","fuel":"가솔린",
     "price":44780000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"팰리세이드 하이브리드","body":"SUV","fuel":"하이브리드",
     "price":50770000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"아이오닉 5","body":"SUV","fuel":"전기",
     "price":47350000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"아이오닉 6","body":"세단","fuel":"전기",
     "price":48560000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"아이오닉 9","body":"SUV","fuel":"전기",
     "price":67590000,"url":HYUNDAI_URL},
    {"brand":"현대","model":"아반떼 N","body":"세단","fuel":"가솔린",
     "price":33560000,"url":HYUNDAI_URL},

    # 제네시스
    {"brand":"제네시스","model":"G70","body":"세단","fuel":"가솔린",
     "price":None,"url":GENESIS_URL},
    {"brand":"제네시스","model":"G80","body":"세단","fuel":"가솔린",
     "price":None,"url":GENESIS_URL},
    {"brand":"제네시스","model":"G90","body":"세단","fuel":"가솔린",
     "price":None,"url":GENESIS_URL},
    {"brand":"제네시스","model":"GV60","body":"SUV","fuel":"전기",
     "price":None,"url":GENESIS_URL},
    {"brand":"제네시스","model":"GV70","body":"SUV","fuel":"가솔린",
     "price":None,"url":GENESIS_URL},
    {"brand":"제네시스","model":"GV80","body":"SUV","fuel":"가솔린",
     "price":None,"url":GENESIS_URL},

    # 기아
    {"brand":"기아","model":"모닝","body":"경차","fuel":"가솔린",
     "price":None,"url":KIA_URL},
    {"brand":"기아","model":"레이","body":"경차","fuel":"가솔린",
     "price":None,"url":KIA_URL},
    {"brand":"기아","model":"K5","body":"세단","fuel":"가솔린",
     "price":None,"url":KIA_URL},
    {"brand":"기아","model":"K8","body":"세단","fuel":"가솔린",
     "price":None,"url":KIA_URL},
    {"brand":"기아","model":"K9","body":"세단","fuel":"가솔린",
     "price":None,"url":KIA_URL},
    {"brand":"기아","model":"셀토스","body":"SUV","fuel":"가솔린",
     "price":None,"url":KIA_URL},
    {"brand":"기아","model":"스포티지","body":"SUV","fuel":"가솔린",
     "price":None,"url":KIA_URL},
    {"brand":"기아","model":"쏘렌토","body":"SUV","fuel":"가솔린",
     "price":None,"url":KIA_URL},
    {"brand":"기아","model":"카니발","body":"MPV","fuel":"가솔린",
     "price":None,"url":KIA_URL},
    {"brand":"기아","model":"EV3","body":"SUV","fuel":"전기",
     "price":None,"url":KIA_URL},
    {"brand":"기아","model":"EV6","body":"SUV","fuel":"전기",
     "price":None,"url":KIA_URL},
    {"brand":"기아","model":"EV9","body":"SUV","fuel":"전기",
     "price":None,"url":KIA_URL},

    # 국내 기타 브랜드
    {"brand":"KGM","model":"티볼리","body":"SUV","fuel":"가솔린",
     "price":None,"url":KG_M_URL},
    {"brand":"KGM","model":"토레스","body":"SUV","fuel":"가솔린",
     "price":None,"url":KG_M_URL},
    {"brand":"KGM","model":"렉스턴","body":"SUV","fuel":"가솔린",
     "price":None,"url":KG_M_URL},
    {"brand":"르노코리아","model":"아르카나","body":"SUV","fuel":"가솔린",
     "price":None,"url":RENAULT_URL},
    {"brand":"르노코리아","model":"그랑 콜레오스","body":"SUV","fuel":"하이브리드",
     "price":None,"url":RENAULT_URL},
    {"brand":"쉐보레","model":"트랙스 크로스오버","body":"SUV","fuel":"가솔린",
     "price":None,"url":CHEVROLET_URL},
    {"brand":"쉐보레","model":"트레일블레이저","body":"SUV","fuel":"가솔린",
     "price":None,"url":CHEVROLET_URL},

    # BMW
    {"brand":"BMW","model":"1시리즈","body":"해치백","fuel":"가솔린",
     "price":None,"url":BMW_URL},
    {"brand":"BMW","model":"3시리즈","body":"세단","fuel":"가솔린",
     "price":None,"url":BMW_URL},
    {"brand":"BMW","model":"5시리즈","body":"세단","fuel":"가솔린",
     "price":None,"url":BMW_URL},
    {"brand":"BMW","model":"7시리즈","body":"세단","fuel":"가솔린",
     "price":None,"url":BMW_URL},
    {"brand":"BMW","model":"X1","body":"SUV","fuel":"가솔린",
     "price":None,"url":BMW_URL},
    {"brand":"BMW","model":"X3","body":"SUV","fuel":"가솔린",
     "price":None,"url":BMW_URL},
    {"brand":"BMW","model":"X5","body":"SUV","fuel":"가솔린",
     "price":None,"url":BMW_URL},
    {"brand":"BMW","model":"i4","body":"세단","fuel":"전기",
     "price":None,"url":BMW_URL},
    {"brand":"BMW","model":"i5","body":"세단","fuel":"전기",
     "price":None,"url":BMW_URL},

    # 메르세데스-벤츠
    {"brand":"메르세데스-벤츠","model":"A-Class","body":"해치백","fuel":"가솔린",
     "price":None,"url":BENZ_URL},
    {"brand":"메르세데스-벤츠","model":"C-Class","body":"세단","fuel":"가솔린",
     "price":None,"url":BENZ_URL},
    {"brand":"메르세데스-벤츠","model":"E-Class","body":"세단","fuel":"가솔린",
     "price":None,"url":BENZ_URL},
    {"brand":"메르세데스-벤츠","model":"S-Class","body":"세단","fuel":"가솔린",
     "price":None,"url":BENZ_URL},
    {"brand":"메르세데스-벤츠","model":"GLA","body":"SUV","fuel":"가솔린",
     "price":None,"url":BENZ_URL},
    {"brand":"메르세데스-벤츠","model":"GLC","body":"SUV","fuel":"가솔린",
     "price":None,"url":BENZ_URL},
    {"brand":"메르세데스-벤츠","model":"GLE","body":"SUV","fuel":"가솔린",
     "price":None,"url":BENZ_URL},
    {"brand":"메르세데스-벤츠","model":"EQS","body":"세단","fuel":"전기",
     "price":None,"url":BENZ_URL},

    # 기타 수입 브랜드
    {"brand":"아우디","model":"A3","body":"세단","fuel":"가솔린",
     "price":None,"url":AUDI_URL},
    {"brand":"아우디","model":"A5","body":"세단","fuel":"가솔린",
     "price":None,"url":AUDI_URL},
    {"brand":"아우디","model":"A6","body":"세단","fuel":"가솔린",
     "price":None,"url":AUDI_URL},
    {"brand":"아우디","model":"Q5","body":"SUV","fuel":"가솔린",
     "price":None,"url":AUDI_URL},
    {"brand":"아우디","model":"Q8 e-tron","body":"SUV","fuel":"전기",
     "price":None,"url":AUDI_URL},

    {"brand":"테슬라","model":"Model 3","body":"세단","fuel":"전기",
     "price":None,"url":TESLA_URL},
    {"brand":"테슬라","model":"Model Y","body":"SUV","fuel":"전기",
     "price":None,"url":TESLA_URL},
    {"brand":"테슬라","model":"Model S","body":"세단","fuel":"전기",
     "price":None,"url":TESLA_URL},
    {"brand":"테슬라","model":"Model X","body":"SUV","fuel":"전기",
     "price":None,"url":TESLA_URL},

    {"brand":"토요타","model":"캠리","body":"세단","fuel":"하이브리드",
     "price":None,"url":TOYOTA_URL},
    {"brand":"토요타","model":"프리우스","body":"해치백","fuel":"하이브리드",
     "price":None,"url":TOYOTA_URL},
    {"brand":"토요타","model":"RAV4","body":"SUV","fuel":"하이브리드",
     "price":None,"url":TOYOTA_URL},

    {"brand":"렉서스","model":"ES","body":"세단","fuel":"하이브리드",
     "price":None,"url":LEXUS_URL},
    {"brand":"렉서스","model":"NX","body":"SUV","fuel":"하이브리드",
     "price":None,"url":LEXUS_URL},
    {"brand":"렉서스","model":"RX","body":"SUV","fuel":"하이브리드",
     "price":None,"url":LEXUS_URL},

    {"brand":"볼보","model":"EX30","body":"SUV","fuel":"전기",
     "price":None,"url":VOLVO_URL},
    {"brand":"볼보","model":"XC60","body":"SUV","fuel":"하이브리드",
     "price":None,"url":VOLVO_URL},
    {"brand":"볼보","model":"XC90","body":"SUV","fuel":"하이브리드",
     "price":None,"url":VOLVO_URL},

    {"brand":"포르쉐","model":"718 카이맨","body":"쿠페","fuel":"가솔린",
     "price":None,"url":PORSCHE_URL},
    {"brand":"포르쉐","model":"911","body":"쿠페","fuel":"가솔린",
     "price":None,"url":PORSCHE_URL},
    {"brand":"포르쉐","model":"타이칸","body":"세단","fuel":"전기",
     "price":None,"url":PORSCHE_URL},
    {"brand":"포르쉐","model":"마칸","body":"SUV","fuel":"가솔린",
     "price":None,"url":PORSCHE_URL},
    {"brand":"포르쉐","model":"카이엔","body":"SUV","fuel":"가솔린",
     "price":None,"url":PORSCHE_URL},

    {"brand":"BYD","model":"돌핀","body":"해치백","fuel":"전기",
     "price":None,"url":BYD_URL},
    {"brand":"BYD","model":"아토 3","body":"SUV","fuel":"전기",
     "price":None,"url":BYD_URL},
    {"brand":"BYD","model":"씰","body":"세단","fuel":"전기",
     "price":None,"url":BYD_URL},
    {"brand":"BYD","model":"씨라이언 7","body":"SUV","fuel":"전기",
     "price":None,"url":BYD_URL},
]

# =========================================================
# 4. 공식 사이트에서 이미지 자동 검색
# =========================================================

class ImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og_image = None
        self.images = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "meta":
            prop = attrs.get("property", "")
            name = attrs.get("name", "")
            if prop == "og:image" or name == "og:image":
                self.og_image = attrs.get("content")

        if tag == "img":
            src = attrs.get("src") or attrs.get("data-src")
            alt = attrs.get("alt", "")
            if src:
                self.images.append((alt, src))


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_official_image(page_url, model_name):
    """
    공식 페이지의 모델 관련 이미지 또는 og:image를 찾습니다.
    사이트 구조 및 접근 정책에 따라 이미지를 못 찾을 수 있습니다.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/124 Safari/537.36"
        )
    }

    try:
        response = requests.get(
            page_url,
            headers=headers,
            timeout=8,
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            return None

        parser = ImageParser()
        parser.feed(response.text)

        # 모델명과 alt 텍스트가 일치하는 이미지 우선
        normalized_model = model_name.lower().replace(" ", "")
        for alt, src in parser.images:
            normalized_alt = alt.lower().replace(" ", "")
            if normalized_model in normalized_alt:
                return requests.compat.urljoin(page_url, src)

        # 일치하는 모델 이미지가 없으면 공식 페이지의 대표 이미지
        if parser.og_image:
            return requests.compat.urljoin(page_url, parser.og_image)

        return None

    except Exception:
        return None


# =========================================================
# 5. 유틸리티
# =========================================================

def won(value):
    if value is None or pd.isna(value):
        return "가격 확인 필요"
    return f"{int(value):,}원"


def short_won(value):
    if value is None or pd.isna(value):
        return "미확인"
    value = int(value)
    if value >= 100_000_000:
        eok = value // 100_000_000
        remainder = value % 100_000_000
        if remainder:
            return f"{eok}억 {remainder // 10_000:,}만원"
        return f"{eok}억원"
    return f"{value // 10_000:,}만원"


def get_price_range(price):
    if price is None:
        return "가격 미확인"
    if price < 30_000_000:
        return "3,000만원 미만"
    if price < 50_000_000:
        return "3,000만~5,000만원"
    if price < 80_000_000:
        return "5,000만~8,000만원"
    if price < 120_000_000:
        return "8,000만~1억 2,000만원"
    return "1억 2,000만원 이상"


# =========================================================
# 6. 헤더
# =========================================================

st.markdown("""
<div class="hero">
    <h1>🚘 AUTOLAB · 자동차 조회 & 튜닝</h1>
    <p>
        국내외 자동차를 비교하고, 나만의 튜닝 예산을 구성해 보세요.<br>
        차량 가격은 기본 판매가격 기준이며, 선택 옵션과 튜닝 비용은 별도로 계산합니다.
    </p>
</div>
""", unsafe_allow_html=True)

# =========================================================
# 7. 사이드바 검색 필터
# =========================================================

df = pd.DataFrame(CARS)

with st.sidebar:
    st.markdown("## 🔎 자동차 찾기")
    st.caption("원하는 조건을 선택하세요.")

    brand_options = ["전체"] + sorted(df["brand"].unique().tolist())
    selected_brand = st.selectbox("자동차 브랜드", brand_options)

    body_options = ["전체"] + sorted(df["body"].unique().tolist())
    selected_body = st.selectbox("차종 / 차체 유형", body_options)

    fuel_options = ["전체"] + sorted(df["fuel"].unique().tolist())
    selected_fuel = st.selectbox("연료", fuel_options)

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

    include_unknown = st.checkbox(
        "가격 미확인 차량도 포함",
        value=True,
    )

    search_text = st.text_input(
        "차량명 검색",
        placeholder="예: 아반떼, Model Y, 5시리즈",
    )

    st.divider()
    st.caption("💡 가격 미확인 차량은 제조사 공식 가격표에서 확인하세요.")

filtered = df.copy()

if selected_brand != "전체":
    filtered = filtered[filtered["brand"] == selected_brand]

if selected_body != "전체":
    filtered = filtered[filtered["body"] == selected_body]

if selected_fuel != "전체":
    filtered = filtered[filtered["fuel"] == selected_fuel]

if search_text.strip():
    q = search_text.strip().lower()
    filtered = filtered[
        filtered["model"].str.lower().str.contains(q, regex=False)
        | filtered["brand"].str.lower().str.contains(q, regex=False)
    ]

if selected_price != "전체":
    if selected_price == "가격 미확인":
        filtered = filtered[filtered["price"].isna()]
    else:
        filtered = filtered[
            filtered["price"].apply(get_price_range) == selected_price
        ]

if not include_unknown and selected_price != "가격 미확인":
    filtered = filtered[filtered["price"].notna()]

# =========================================================
# 8. 차량 목록
# =========================================================

st.markdown('<div class="section-title">🚗 차량 목록</div>', unsafe_allow_html=True)

st.caption(
    f"현재 조건에 맞는 차량: {len(filtered)}대 · "
    "가격은 옵션을 제외한 기본 시작 가격이며 세금·보조금·프로모션에 따라 달라질 수 있습니다."
)

if filtered.empty:
    st.info("검색 조건에 맞는 차량이 없습니다. 필터를 변경해 보세요.")

else:
    vehicle_labels = [
        f"{row['brand']} · {row['model']}"
        for _, row in filtered.iterrows()
    ]

    selected_label = st.selectbox(
        "상세 조회할 차량 선택",
        vehicle_labels,
        key="selected_vehicle",
    )

    selected_index = vehicle_labels.index(selected_label)
    car = filtered.iloc[selected_index].to_dict()

    left, right = st.columns([1.05, 1])

    with left:
        st.markdown('<div class="vehicle-card">', unsafe_allow_html=True)

        st.markdown(
            f"<div class='vehicle-meta'>{html.escape(car['brand'])} · "
            f"{html.escape(car['body'])} · "
            f"{html.escape(car['fuel'])}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='vehicle-name'>{html.escape(car['model'])}</div>",
            unsafe_allow_html=True,
        )

        if car["price"] is not None:
            st.markdown(
                f"<div class='price'>{won(car['price'])}부터</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div class='unknown-price'>공식 기본 가격 확인 필요</div>",
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)

        st.link_button(
            "🏢 제조사 공식 사이트에서 확인",
            car["url"],
            use_container_width=True,
        )

    with right:
        st.markdown("#### 🖼️ 공식 차량 이미지")

        with st.spinner("공식 사이트에서 차량 이미지를 확인하는 중..."):
            image_url = fetch_official_image(
                car["url"],
                car["model"],
            )

        if image_url:
            try:
                st.image(
                    image_url,
                    caption=f"{car['brand']} · {car['model']} — 공식 페이지 이미지",
                    use_container_width=True,
                )
            except Exception:
                st.info("이미지를 표시할 수 없습니다. 공식 사이트에서 확인해 주세요.")
        else:
            st.markdown("""
            <div class="preview" style="text-align:center;padding:40px 15px;">
                <div style="font-size:64px;">🚘</div>
                <div style="font-size:17px;font-weight:800;margin-top:12px;">
                    차량 이미지 확인 필요
                </div>
                <div style="font-size:13px;color:#64748b;margin-top:8px;">
                    제조사 사이트의 이미지 접근이 제한될 수 있습니다.
                </div>
            </div>
            """, unsafe_allow_html=True)

# =========================================================
# 9. 튜닝 구성
# =========================================================

st.divider()
st.markdown(
    '<div class="section-title">🛠️ 나만의 튜닝 구성하기</div>',
    unsafe_allow_html=True,
)

st.markdown("""
<div class="notice">
    아래 튜닝 비용은 실제 업체의 공식 견적이 아닌 예산 계획용 예시입니다.
    부품 브랜드, 차종, 공임, 인증 및 구조변경 필요 여부에 따라 달라집니다.
</div>
""", unsafe_allow_html=True)

tuning_defaults = {
    "외관": {
        "description": "바디킷, 스포일러, 랩핑 등 외관 스타일",
        "cost": 1_000_000,
    },
    "휠·타이어": {
        "description": "휠 디자인 및 타이어 교체 예산",
        "cost": 1_500_000,
    },
    "서스펜션": {
        "description": "승차감·차고 조절 관련 부품 예산",
        "cost": 1_200_000,
    },
    "실내": {
        "description": "실내 트림, 매트, 장식 및 편의 요소",
        "cost": 500_000,
    },
}

tuning_selected = st.multiselect(
    "원하는 튜닝 항목을 선택하세요.",
    list(tuning_defaults.keys()),
    default=[],
)

tuning_costs = {}

if tuning_selected:
    st.markdown("#### 💰 항목별 예상 비용")
    cost_columns = st.columns(min(len(tuning_selected), 2))

    for i, item in enumerate(tuning_selected):
        with cost_columns[i % len(cost_columns)]:
            tuning_costs[item] = st.number_input(
                f"{item} 비용 (원)",
                min_value=0,
                max_value=100_000_000,
                value=tuning_defaults[item]["cost"],
                step=100_000,
                key=f"tuning_cost_{item}",
                help=tuning_defaults[item]["description"],
            )
            st.caption(tuning_defaults[item]["description"])

tuning_total = sum(tuning_costs.values())
base_price = car["price"] if "car" in locals() else None

st.divider()
st.markdown("#### 🧾 예상 비용 요약")

m1, m2, m3 = st.columns(3)

with m1:
    st.metric(
        "차량 기본 가격",
        short_won(base_price),
    )

with m2:
    st.metric(
        "선택한 튜닝 비용",
        won(tuning_total),
        help="사용자가 설정한 예산의 합계입니다.",
    )

with m3:
    if base_price is not None:
        st.metric(
            "차량 + 튜닝 예상 합계",
            won(base_price + tuning_total),
        )
    else:
        st.metric(
            "차량 + 튜닝 예상 합계",
            "차량 가격 확인 필요",
        )

if tuning_selected:
    cost_df = pd.DataFrame([
        {
            "튜닝 항목": item,
            "설명": tuning_defaults[item]["description"],
            "예상 비용": tuning_costs[item],
        }
        for item in tuning_selected
    ])

    st.dataframe(
        cost_df,
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
    st.info("튜닝 항목을 선택하면 예상 비용이 여기에 표시됩니다.")

# =========================================================
# 10. 튜닝 시각화 미리보기
# =========================================================

st.divider()
st.markdown(
    '<div class="section-title">🎨 튜닝 스타일 미리보기</div>',
    unsafe_allow_html=True,
)

st.caption(
    "이 영역은 선택한 튜닝 구성을 정리하는 시각화 보드입니다. "
    "차량 사진 자체를 편집하거나 실제 장착 결과를 시뮬레이션한 이미지는 아닙니다."
)

preview_left, preview_right = st.columns([1, 1])

with preview_left:
    if "car" in locals() and image_url:
        st.image(image_url, use_container_width=True)
    else:
        st.markdown("""
        <div class="preview" style="text-align:center;padding:35px;">
            <div style="font-size:65px;">🚙</div>
            <div class="preview-title">나의 튜닝 프로젝트</div>
            <p style="color:#64748b;">차량 이미지는 공식 사이트에서 확인해 주세요.</p>
        </div>
        """, unsafe_allow_html=True)

with preview_right:
    st.markdown('<div class="preview">', unsafe_allow_html=True)
    st.markdown(
        f"<div class='preview-title'>{html.escape(car['model'] if 'car' in locals() else '선택 차량')}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='color:#64748b'>{html.escape(car['brand'] if 'car' in locals() else '')} · 튜닝 구성</p>",
        unsafe_allow_html=True,
    )

    if tuning_selected:
        tags = "".join(
            f"<span class='preview-tag'>{html.escape(item)}</span>"
            for item in tuning_selected
        )
        st.markdown(tags, unsafe_allow_html=True)
        st.markdown("---")
        for item in tuning_selected:
            st.write(
                f"🔧 **{item}** — {won(tuning_costs[item])}"
            )
    else:
        st.write("아직 선택한 튜닝 항목이 없습니다.")

    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# 11. 유의사항 및 출처
# =========================================================

st.divider()
st.markdown("### 📌 이용 안내")

st.markdown("""
- **가격:** 가격이 표시된 차량도 실제 계약 전 제조사 공식 가격표에서 트림과 기준일을 확인하세요.
- **미확인 가격:** 가격 정보가 등록되지 않은 차량은 0원으로 계산하지 않습니다. 차량 기본 가격을 확인한 뒤 합계를 판단하세요.
- **이미지:** 공식 사이트의 대표 이미지 또는 모델 이미지를 자동으로 읽습니다. 제조사의 접근 제한이나 페이지 구조 변경으로 이미지가 나오지 않을 수 있습니다.
- **튜닝:** 실제 부품 장착 여부, 차량 보증, 안전성, 배출가스 기준, 소음 기준 및 관련 법규를 확인한 후 진행하세요.
- **시각화:** 튜닝 미리보기는 선택 항목을 보여주는 구성 보드이며 실제 차량의 외관 변경을 합성한 사진이 아닙니다.
""")

st.markdown("#### 공식 사이트")
official_brands = {
    "현대자동차": HYUNDAI_URL,
    "기아": KIA_URL,
    "제네시스 가격표·카탈로그": GENESIS_URL,
    "KGM": KG_M_URL,
    "르노코리아": RENAULT_URL,
    "쉐보레": CHEVROLET_URL,
    "BMW": BMW_URL,
    "메르세데스-벤츠": BENZ_URL,
    "아우디": AUDI_URL,
    "테슬라": TESLA_URL,
    "토요타": TOYOTA_URL,
    "렉서스": LEXUS_URL,
    "볼보": VOLVO_URL,
    "포르쉐": PORSCHE_URL,
    "BYD": BYD_URL,
}

link_cols = st.columns(3)
for i, (brand_name, brand_url) in enumerate(official_brands.items()):
    with link_cols[i % 3]:
        st.markdown(f"- [{brand_name}]({brand_url})")

st.caption(
    f"오토랩 · 자동차 조회 및 튜닝 예산 도구 · "
    f"화면 생성 시각 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
)
