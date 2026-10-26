
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
# 2. 디자인
# =========================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', sans-serif;
}
.stApp {
    background: #ffffff;
    color: #172033;
}
.block-container {
    max-width: 1500px;
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}
.hero {
    padding: 30px 34px;
    border-radius: 20px;
    background: linear-gradient(120deg, #17283f, #315d83);
    color: white;
    margin-bottom: 26px;
}
.hero h1 {
    color: white;
    font-size: 34px;
    font-weight: 800;
    margin: 0 0 8px;
}
.hero p {
    color: #dce8f5;
    margin: 0;
    line-height: 1.8;
}
.section-title {
    font-size: 25px;
    font-weight: 800;
    margin: 18px 0 12px;
}
.vehicle-card {
    background: white;
    border-radius: 15px;
    padding: 12px 10px 16px;
    text-align: center;
    height: 100%;
    transition: background .2s ease, box-shadow .2s ease;
}
.vehicle-card:hover {
    background: #fafbfc;
    box-shadow: 0 5px 20px rgba(15, 30, 50, .08);
}
.vehicle-name {
    color: #111827;
    font-size: 19px;
    font-weight: 750;
    margin: 10px 0 5px;
}
.vehicle-price {
    color: #65748b;
    font-size: 16px;
    margin-bottom: 8px;
}
.vehicle-meta {
    color: #8993a2;
    font-size: 12px;
    margin-bottom: 12px;
}
.price-big {
    font-size: 25px;
    color: #1765c0;
    font-weight: 800;
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
    background: #fff;
    border: 1px solid #e5e9f0;
    border-radius: 13px;
    padding: 14px;
}
div.stButton > button, div.stLinkButton > a {
    border-radius: 9px;
    font-weight: 650;
}
div[data-testid="stSidebar"] {
    background: #f5f7fa;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# 3. 공식 사이트
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

# =========================================================
# 4. 차량 데이터
#
# 가격이 확인되지 않은 모델은 None으로 둡니다.
# 아래 가격을 임의의 공식 가격으로 간주하지 않습니다.
# =========================================================
RAW_CARS = [
    ("기아", "레이 EV", "경차", "전기", 28070000),
    ("기아", "EV3", "SUV", "전기", 39950000),
    ("기아", "EV3 GT", "SUV", "전기", 53750000),
    ("기아", "EV4", "세단", "전기", 40420000),
    ("기아", "EV4 GT", "세단", "전기", 55170000),
    ("기아", "EV5", "SUV", "전기", 41550000),
    ("기아", "모닝", "경차", "가솔린", None),
    ("기아", "레이", "경차", "가솔린", None),
    ("기아", "K5", "세단", "가솔린", None),
    ("기아", "K8", "세단", "가솔린", None),
    ("기아", "K9", "세단", "가솔린", None),
    ("기아", "셀토스", "SUV", "가솔린", None),
    ("기아", "스포티지", "SUV", "가솔린", None),
    ("기아", "쏘렌토", "SUV", "가솔린", None),
    ("기아", "카니발", "MPV", "가솔린", None),
    ("기아", "EV6", "SUV", "전기", None),
    ("기아", "EV9", "SUV", "전기", None),

    ("현대", "캐스퍼 일렉트릭", "경차", "전기", None),
    ("현대", "아반떼", "세단", "가솔린", None),
    ("현대", "아반떼 하이브리드", "세단", "하이브리드", None),
    ("현대", "쏘나타 디 엣지", "세단", "가솔린", None),
    ("현대", "그랜저", "세단", "가솔린", None),
    ("현대", "그랜저 하이브리드", "세단", "하이브리드", None),
    ("현대", "베뉴", "SUV", "가솔린", None),
    ("현대", "코나", "SUV", "가솔린", None),
    ("현대", "코나 하이브리드", "SUV", "하이브리드", None),
    ("현대", "투싼", "SUV", "가솔린", None),
    ("현대", "싼타페", "SUV", "가솔린", None),
    ("현대", "팰리세이드", "SUV", "가솔린", None),
    ("현대", "아이오닉 5", "SUV", "전기", None),
    ("현대", "아이오닉 6", "세단", "전기", None),
    ("현대", "아이오닉 9", "SUV", "전기", None),
    ("현대", "아반떼 N", "세단", "가솔린", None),

    ("제네시스", "G70", "세단", "가솔린", None),
    ("제네시스", "G80", "세단", "가솔린", None),
    ("제네시스", "G90", "세단", "가솔린", None),
    ("제네시스", "GV60", "SUV", "전기", None),
    ("제네시스", "GV70", "SUV", "가솔린", None),
    ("제네시스", "GV80", "SUV", "가솔린", None),

    ("KGM", "티볼리", "SUV", "가솔린", None),
    ("KGM", "토레스", "SUV", "가솔린", None),
    ("KGM", "렉스턴", "SUV", "가솔린", None),

    ("르노코리아", "아르카나", "SUV", "하이브리드", None),
    ("르노코리아", "그랑 콜레오스", "SUV", "하이브리드", None),

    ("쉐보레", "트랙스 크로스오버", "SUV", "가솔린", None),
    ("쉐보레", "트레일블레이저", "SUV", "가솔린", None),

    ("BMW", "1시리즈", "해치백", "가솔린", None),
    ("BMW", "3시리즈", "세단", "가솔린", None),
    ("BMW", "5시리즈", "세단", "가솔린", None),
    ("BMW", "7시리즈", "세단", "가솔린", None),
    ("BMW", "X1", "SUV", "가솔린", None),
    ("BMW", "X3", "SUV", "가솔린", None),
    ("BMW", "X5", "SUV", "가솔린", None),
    ("BMW", "i4", "세단", "전기", None),
    ("BMW", "i5", "세단", "전기", None),

    ("메르세데스-벤츠", "A-Class", "해치백", "가솔린", None),
    ("메르세데스-벤츠", "C-Class", "세단", "가솔린", None),
    ("메르세데스-벤츠", "E-Class", "세단", "가솔린", None),
    ("메르세데스-벤츠", "S-Class", "세단", "가솔린", None),
    ("메르세데스-벤츠", "GLA", "SUV", "가솔린", None),
    ("메르세데스-벤츠", "GLC", "SUV", "가솔린", None),
    ("메르세데스-벤츠", "GLE", "SUV", "가솔린", None),
    ("메르세데스-벤츠", "EQS", "세단", "전기", None),

    ("아우디", "A3", "세단", "가솔린", None),
    ("아우디", "A5", "세단", "가솔린", None),
    ("아우디", "A6", "세단", "가솔린", None),
    ("아우디", "Q5", "SUV", "가솔린", None),
    ("아우디", "Q8 e-tron", "SUV", "전기", None),

    ("테슬라", "Model 3", "세단", "전기", None),
    ("테슬라", "Model Y", "SUV", "전기", None),
    ("테슬라", "Model S", "세단", "전기", None),
    ("테슬라", "Model X", "SUV", "전기", None),

    ("토요타", "캠리", "세단", "하이브리드", None),
    ("토요타", "프리우스", "해치백", "하이브리드", None),
    ("토요타", "RAV4", "SUV", "하이브리드", None),

    ("렉서스", "ES", "세단", "하이브리드", None),
    ("렉서스", "NX", "SUV", "하이브리드", None),
    ("렉서스", "RX", "SUV", "하이브리드", None),

    ("볼보", "EX30", "SUV", "전기", None),
    ("볼보", "XC60", "SUV", "하이브리드", None),
    ("볼보", "XC90", "SUV", "하이브리드", None),

    ("포르쉐", "718 카이맨", "쿠페", "가솔린", None),
    ("포르쉐", "911", "쿠페", "가솔린", None),
    ("포르쉐", "타이칸", "세단", "전기", None),
    ("포르쉐", "마칸", "SUV", "가솔린", None),
    ("포르쉐", "카이엔", "SUV", "가솔린", None),

    ("BYD", "돌핀", "해치백", "전기", None),
    ("BYD", "아토 3", "SUV", "전기", None),
    ("BYD", "씰", "세단", "전기", None),
    ("BYD", "씨라이언 7", "SUV", "전기", None),
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
# 5. 이미지 추출
# =========================================================
class ImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "meta":
            if attrs.get("property") == "og:image":
                src = attrs.get("content")
                if src:
                    self.images.append({
                        "src": src,
                        "alt": "",
                        "title": "",
                    })

        if tag == "img":
            src = (
                attrs.get("src")
                or attrs.get("data-src")
                or attrs.get("data-original")
                or attrs.get("data-lazy-src")
            )
            if src:
                self.images.append({
                    "src": src,
                    "alt": attrs.get("alt", ""),
                    "title": attrs.get("title", ""),
                })


def normalize_text(text):
    return re.sub(r"[^a-zA-Z0-9가-힣]", "", str(text)).lower()


def find_angle(item, model):
    text = " ".join([
        item.get("alt", ""),
        item.get("title", ""),
        item.get("src", ""),
    ]).lower()

    if normalize_text(model) not in normalize_text(text):
        return None

    front_terms = [
        "front", "frontview", "frontthreequarter",
        "threequarter", "3quarter", "정면", "전면",
        "대각선", "사선",
    ]
    side_terms = [
        "sideview", "side-view", "side", "profile",
        "lateral", "측면", "옆면",
    ]

    is_front = any(term in text for term in front_terms)
    is_side = any(term in text for term in side_terms)

    if is_front and not is_side:
        return "front"
    if is_side and not is_front:
        return "side"
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_angle_images(page_url, model):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(
            page_url,
            headers=headers,
            timeout=8,
        )
        response.raise_for_status()

        parser = ImageParser()
        parser.feed(response.text)

        result = {"side": None, "front": None}

        for item in parser.images:
            src = urljoin(page_url, item["src"])
            item["src"] = src

            angle = find_angle(item, model)
            if angle and not result[angle]:
                result[angle] = src

        return result

    except Exception:
        return {"side": None, "front": None}


# =========================================================
# 6. 이미지 출력
# =========================================================
def show_car_angle_view(side_url, front_url, height=230):
    if not side_url:
        st.markdown("""
        <div style="
            height:230px;display:flex;flex-direction:column;
            justify-content:center;align-items:center;
            background:#f7f8fa;border-radius:12px;color:#738094;">
            <div style="font-size:54px;">🚘</div>
            <b>차량 이미지 확인 필요</b>
            <span style="font-size:12px;margin-top:6px;">
                공식 사이트에서 사진을 찾지 못했습니다.
            </span>
        </div>
        """, unsafe_allow_html=True)
        return

    if not front_url:
        st.image(side_url, use_container_width=True)
        return

    side = html.escape(side_url, quote=True)
    front = html.escape(front_url, quote=True)

    components.html(
        f"""
        <div class="car-view">
          <img class="side" src="{side}" alt="차량 측면">
          <img class="front" src="{front}" alt="차량 대각선 정면">
          <span class="hint">마우스를 올려 정면 보기 ↗</span>
        </div>
        <style>
        body {{margin:0;padding:0;background:transparent;}}
        .car-view {{
            position:relative;width:100%;height:{height}px;
            overflow:hidden;border-radius:12px;
            background:#fff;cursor:pointer;
        }}
        .car-view img {{
            position:absolute;inset:0;width:100%;height:100%;
            object-fit:contain;
            transition:opacity .4s ease,transform .4s ease;
        }}
        .car-view .side {{opacity:1;transform:scale(1);}}
        .car-view .front {{opacity:0;transform:scale(.96);}}
        .car-view:hover .side {{opacity:0;transform:scale(.96);}}
        .car-view:hover .front {{opacity:1;transform:scale(1);}}
        .hint {{
            position:absolute;right:8px;bottom:8px;
            color:white;background:#17283fcc;
            border-radius:20px;padding:6px 10px;font-size:11px;
        }}
        </style>
        """,
        height=height + 5,
        scrolling=False,
    )


def won(value):
    if value is None or pd.isna(value):
        return "가격 확인 필요"
    return f"{int(value):,}원"


def price_bucket(value):
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


# =========================================================
# 7. 헤더
# =========================================================
st.markdown("""
<div class="hero">
    <h1>🚘 AUTOLAB</h1>
    <p>
        국내외 자동차를 찾아보고, 나만의 튜닝 구성을 만들어 보세요.<br>
        차량 카드를 선택하면 상세 정보와 예상 비용을 확인할 수 있습니다.
    </p>
</div>
""", unsafe_allow_html=True)

# =========================================================
# 8. 필터
# =========================================================
df = pd.DataFrame(CARS)

with st.sidebar:
    st.title("🔎 차량 검색")

    brand_options = ["전체"] + sorted(df["brand"].unique().tolist())
    selected_brand = st.selectbox("브랜드", brand_options)

    body_options = ["전체"] + sorted(df["body"].unique().tolist())
    selected_body = st.selectbox("차체 유형", body_options)

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

    search_query = st.text_input("모델명 검색", placeholder="예: EV3, 아반떼")

    st.caption("※ 차량 기본 가격은 선택 옵션을 제외한 가격입니다.")

filtered = df.copy()

if selected_brand != "전체":
    filtered = filtered[filtered["brand"] == selected_brand]

if selected_body != "전체":
    filtered = filtered[filtered["body"] == selected_body]

if selected_fuel != "전체":
    filtered = filtered[filtered["fuel"] == selected_fuel]

if selected_price != "전체":
    filtered = filtered[
        filtered["price"].apply(price_bucket) == selected_price
    ]

if search_query.strip():
    q = search_query.strip().lower()
    filtered = filtered[
        filtered["model"].str.lower().str.contains(q, regex=False)
        | filtered["brand"].str.lower().str.contains(q, regex=False)
    ]

# =========================================================
# 9. 검색 결과 3열 카드 목록
# =========================================================
st.markdown(
    '<div class="section-title">🚗 검색된 차량</div>',
    unsafe_allow_html=True,
)
st.caption(f"검색 결과 {len(filtered)}대")

if filtered.empty:
    st.info("검색 조건에 맞는 차량이 없습니다. 검색 조건을 변경해 주세요.")
else:
    per_row = 3

    for start in range(0, len(filtered), per_row):
        chunk = filtered.iloc[start:start + per_row]
        columns = st.columns(per_row, gap="large")

        for column, (_, vehicle) in zip(columns, chunk.iterrows()):
            with column:
                brand_name = str(vehicle["brand"])
                model_name = str(vehicle["model"])
                vehicle_url = str(vehicle["url"])

                images = fetch_angle_images(vehicle_url, model_name)

                st.markdown(
                    '<div class="vehicle-card">',
                    unsafe_allow_html=True,
                )

                show_car_angle_view(
                    images["side"],
                    images["front"],
                    height=230,
                )

                st.markdown(
                    f'<div class="vehicle-name">'
                    f'{html.escape(model_name)}</div>',
                    unsafe_allow_html=True,
                )

                if vehicle["price"] is None or pd.isna(vehicle["price"]):
                    price_label = "가격 확인 필요"
                else:
                    price_label = f'{int(vehicle["price"]):,}원 ~'

                st.markdown(
                    f'<div class="vehicle-price">'
                    f'{price_label}</div>',
                    unsafe_allow_html=True,
                )

                st.markdown(
                    f'<div class="vehicle-meta">'
                    f'{html.escape(brand_name)} · '
                    f'{html.escape(str(vehicle["body"]))} · '
                    f'{html.escape(str(vehicle["fuel"]))}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                st.markdown("</div>", unsafe_allow_html=True)

                detail_key = f"detail_{brand_name}_{model_name}"

                if st.button(
                    "상세 정보 및 튜닝",
                    key=detail_key,
                    use_container_width=True,
                ):
                    st.session_state["selected_vehicle"] = (
                        f"{brand_name}|||{model_name}"
                    )
                    st.rerun()

                st.link_button(
                    "제조사 공식 사이트",
                    vehicle_url,
                    use_container_width=True,
                )

# =========================================================
# 10. 선택한 차량의 상세 정보
# =========================================================
st.divider()
st.markdown(
    '<div class="section-title">🧰 차량 상세 정보 & 튜닝</div>',
    unsafe_allow_html=True,
)

vehicle_keys = [
    f"{r['brand']}|||{r['model']}" for r in CARS
]

current_selection = st.session_state.get("selected_vehicle")

if current_selection not in vehicle_keys:
    current_selection = vehicle_keys[0]

selected_key = st.selectbox(
    "튜닝할 차량 선택",
    vehicle_keys,
    index=vehicle_keys.index(current_selection),
    format_func=lambda key: key.replace("|||", " · "),
)

selected_car = next(
    car for car in CARS
    if f"{car['brand']}|||{car['model']}" == selected_key
)

detail_left, detail_right = st.columns([1, 1], gap="large")

with detail_left:
    st.subheader(f"{selected_car['brand']} {selected_car['model']}")

    st.write(f"차체 유형: **{selected_car['body']}**")
    st.write(f"연료: **{selected_car['fuel']}**")

    if selected_car["price"] is None:
        st.warning("기본 가격을 확인하지 못했습니다. 공식 가격표를 확인해 주세요.")
    else:
        st.markdown(
            f'<div class="price-big">{won(selected_car["price"])}</div>',
            unsafe_allow_html=True,
        )

    st.caption("옵션 가격은 기본 차량 가격에 포함하지 않습니다.")

    st.link_button(
        "공식 사이트에서 차량 확인",
        selected_car["url"],
        use_container_width=True,
    )

with detail_right:
    detail_images = fetch_angle_images(
        selected_car["url"],
        selected_car["model"],
    )
    show_car_angle_view(
        detail_images["side"],
        detail_images["front"],
        height=300,
    )

# =========================================================
# 11. 튜닝 항목 및 비용 계산
# =========================================================
st.markdown("### 🛠️ 튜닝 항목 선택")

st.markdown("""
<div class="notice">
    튜닝 금액은 직접 조절하는 예산 예시입니다. 실제 부품 가격이나
    장착 업체의 확정 견적이 아니므로 작업 전 별도 확인이 필요합니다.
</div>
""", unsafe_allow_html=True)

TUNING = {
    "외관": {
        "description": "바디킷, 스포일러, 랩핑 등",
        "default": 1_000_000,
    },
    "휠·타이어": {
        "description": "휠 및 타이어 교체",
        "default": 1_500_000,
    },
    "서스펜션": {
        "description": "서스펜션 및 차고 조절 관련 부품",
        "default": 1_200_000,
    },
    "실내": {
        "description": "실내 트림, 매트, 장식",
        "default": 500_000,
    },
}

chosen_tuning = st.multiselect(
    "원하는 튜닝 항목",
    options=list(TUNING.keys()),
    default=[],
)

costs = {}

if chosen_tuning:
    cost_columns = st.columns(2)

    for index, item in enumerate(chosen_tuning):
        with cost_columns[index % 2]:
            costs[item] = st.number_input(
                f"{item} 예상 비용 (원)",
                min_value=0,
                max_value=100_000_000,
                value=TUNING[item]["default"],
                step=100_000,
                key=f"tuning_cost_{item}",
            )
            st.caption(TUNING[item]["description"])

tuning_total = sum(costs.values())
base_price = selected_car["price"]

st.markdown("### 💰 예상 비용")

metric1, metric2, metric3 = st.columns(3)

with metric1:
    st.metric("차량 기본 가격", won(base_price))

with metric2:
    st.metric("튜닝 예산", won(tuning_total))

with metric3:
    if base_price is not None:
        st.metric("차량 + 튜닝 합계", won(base_price + tuning_total))
    else:
        st.metric("차량 + 튜닝 합계", "기본 가격 확인 필요")

if chosen_tuning:
    st.dataframe(
        pd.DataFrame([
            {
                "항목": item,
                "설명": TUNING[item]["description"],
                "예상 비용": f"{costs[item]:,}원",
            }
            for item in chosen_tuning
        ]),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("튜닝 항목을 선택하면 예상 비용이 계산됩니다.")

# =========================================================
# 12. 공식 사이트 모음
# =========================================================
with st.expander("🌐 전체 브랜드 공식 사이트"):
    for brand_name, brand_url in URLS.items():
        st.markdown(f"- [{brand_name}]({brand_url})")

st.divider()
st.caption(
    "AUTOLAB · 가격과 이미지는 제조사 공식 자료를 우선하며, "
    "확인되지 않은 정보는 별도 확인이 필요합니다."
)
