
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup


# =====================================================
# 웹소설 통합 랭킹 TOP 100
# =====================================================

st.set_page_config(
    page_title="웹소설 통합 랭킹 TOP 100",
    page_icon="📚",
    layout="wide",
)

KST = ZoneInfo("Asia/Seoul")
TODAY = datetime.now(KST).date()
YESTERDAY = TODAY - timedelta(days=1)

PLATFORMS = [
    "전체 플랫폼",
    "네이버시리즈",
    "카카오페이지",
    "문피아",
]

PERIODS = ["일간", "주간", "월간"]
METRICS = ["평점순", "좋아요율순"]

URLS = {
    "네이버시리즈": {
        "일간": "https://series.naver.com/novel/top100List.series?categoryCode=ALL&rankingTypeCode=DAILY",
        "주간": "https://series.naver.com/novel/top100List.series?categoryCode=ALL&rankingTypeCode=WEEKLY",
        "월간": "https://series.naver.com/novel/top100List.series?categoryCode=ALL&rankingTypeCode=MONTHLY",
    },
    "카카오페이지": {
        "일간": "https://page.kakao.com/landing/ranking/0",
        "주간": "https://page.kakao.com/landing/ranking/0",
        "월간": "https://page.kakao.com/landing/ranking/0",
    },
    "문피아": {
        "일간": "https://www.munpia.com/best/today",
        "주간": "https://www.munpia.com/best/plsa.weekly",
        "월간": "https://www.munpia.com/best/plsa.monthly",
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

# 메뉴나 이벤트 이름은 작품명으로 사용하지 않습니다.
BAD_TITLES = {
    "타임딜", "매일10시무료", "무료", "프리패스",
    "웹소설", "웹툰", "인기 단행본", "TOP 100",
    "로그인", "회원가입", "고객센터", "공지사항",
    "이벤트", "검색", "홈", "랭킹", "더보기",
    "오늘의 베스트", "주간 베스트", "월간 베스트",
    "전체", "일간", "주간", "월간",
}


# =====================================================
# 간단한 화면 디자인
# =====================================================

st.markdown("""
<style>
.stApp {
    background-color: #fffaf2;
}
h1 {
    color: #59412e;
    letter-spacing: -1px;
}
div[data-testid="stMetric"] {
    background: #fff0d6;
    border: 1px solid #f0d9b3;
    border-radius: 12px;
    padding: 12px;
}
</style>
""", unsafe_allow_html=True)


# =====================================================
# 왼쪽 설정 창
# =====================================================

with st.sidebar:
    st.title("📚 웹소설 랭킹")

    with st.expander("⚙️ 조회 설정", expanded=True):
        platform = st.selectbox("플랫폼", PLATFORMS)
        period = st.radio("기간", PERIODS, horizontal=True)
        metric = st.radio("순위 기준", METRICS)

        count = st.select_slider(
            "표시 개수",
            options=[10, 20, 50, 100],
            value=100,
            format_func=lambda x: f"TOP {x}",
        )

    st.caption(f"한국 시간 기준 어제: {YESTERDAY:%Y-%m-%d}")

    if st.button("🔄 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# =====================================================
# 숫자 변환
# =====================================================

def parse_number(value):
    """12,345 / 1.2만 / 3억 같은 숫자를 숫자로 변환합니다."""
    if not value:
        return None

    value = value.strip().replace(",", "").replace(" ", "")

    match = re.search(r"(\d+(?:\.\d+)?)\s*(억|만|천)?", value)
    if not match:
        return None

    number = float(match.group(1))
    unit = match.group(2)

    if unit == "억":
        number *= 100_000_000
    elif unit == "만":
        number *= 10_000
    elif unit == "천":
        number *= 1_000

    return number


def clean_title(value):
    value = re.sub(r"\s+", " ", value or "").strip()
    value = value.replace("\u200b", "").replace("\ufeff", "")
    return value.strip(" |·•\n\t")


def valid_title(title):
    """메뉴 문구나 빈 제목을 작품으로 등록하지 않습니다."""
    title = clean_title(title)

    if not 2 <= len(title) <= 100:
        return False

    if title in BAD_TITLES:
        return False

    if any(word in title for word in [
        "로그인", "회원가입", "고객센터", "무료충전",
        "이용약관", "개인정보처리방침",
    ]):
        return False

    if title.lower().startswith(("http://", "https://", "javascript:")):
        return False

    return True


# =====================================================
# 페이지 가져오기
# =====================================================

@st.cache_data(ttl=900, show_spinner=False)
def fetch_html(url):
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def add_page_number(url, page):
    """페이지 번호를 지원하는 주소에 페이지 번호를 붙입니다."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query["page"] = [str(page)]

    return urlunparse(
        parsed._replace(query=urlencode(query, doseq=True))
    )


# =====================================================
# 작품 제목과 지표 추출
# =====================================================

def title_from_link(a):
    """링크 제목, title 속성, 이미지 대체 텍스트를 차례로 확인합니다."""
    candidates = [
        a.get_text(" ", strip=True),
        a.get("title", ""),
        a.get("aria-label", ""),
    ]

    img = a.find("img")
    if img:
        candidates.append(img.get("alt", ""))

    for candidate in candidates:
        candidate = clean_title(candidate)
        if valid_title(candidate):
            return candidate

    return ""


def card_text_from_link(a):
    """
    작품 링크 주변의 카드 텍스트를 찾아 평점, 조회수, 좋아요를 확인합니다.
    가장 가까운 영역부터 확인하여 다른 작품의 숫자를 섞을 가능성을 줄입니다.
    """
    current = a
    candidates = []

    for _ in range(7):
        if current is None:
            break

        text = current.get_text(" ", strip=True)

        if text and len(text) <= 1500:
            candidates.append(text)

        current = current.parent

    # 평점 또는 조회수 정보가 포함된 가장 가까운 영역을 선택합니다.
    for text in candidates:
        if re.search(r"평점\s*[:：]?\s*\d+(?:\.\d+)?", text):
            return text

        if re.search(r"(?:조회수?|좋아요)\s*[:：]?\s*[\d,.]+", text):
            return text

    return candidates[0] if candidates else ""


def extract_metrics(text):
    """작품 카드 텍스트에서 평점, 조회수, 좋아요 수를 추출합니다."""
    rating = None
    views = None
    likes = None

    # 평점 9.7
    match = re.search(r"평점\s*[:：]?\s*(\d+(?:\.\d+)?)", text)
    if match:
        rating = float(match.group(1))

    # 조회 12,345 / 조회수 1.2만
    match = re.search(
        r"조회수?\s*[:：]?\s*([\d,.]+\s*(?:억|만|천)?)",
        text,
    )
    if match:
        views = parse_number(match.group(1))

    # 좋아요 123 / 좋아요 수 1.2만
    match = re.search(
        r"좋아요(?:\s*수)?\s*[:：]?\s*([\d,.]+\s*(?:억|만|천)?)",
        text,
    )
    if match:
        likes = parse_number(match.group(1))

    return rating, views, likes


def extract_original_rank(text):
    """원본 페이지에 명시된 순위가 있을 때만 읽습니다."""
    match = re.search(r"(?:^|\s)(100|[1-9]?\d)\s*위(?:\s|$)", text)

    if match:
        rank = int(match.group(1))
        if 1 <= rank <= 100:
            return rank

    return None


# =====================================================
# 플랫폼별 작품 링크 검사
# =====================================================

def valid_work_link(platform_name, href):
    parsed = urlparse(href)
    path = parsed.path.lower()

    if platform_name == "네이버시리즈":
        return (
            parsed.netloc.endswith("series.naver.com")
            and "/novel/detail" in path
        )

    if platform_name == "카카오페이지":
        return (
            parsed.netloc == "page.kakao.com"
            and bool(re.search(r"/content/\d+", path))
        )

    if platform_name == "문피아":
        return (
            parsed.netloc.endswith("munpia.com")
            and "/novel/" in path
            and "/best/" not in path
        )

    return False


def parse_page(html, platform_name, source_url):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(source_url, a["href"])

        if not valid_work_link(platform_name, href):
            continue

        title = title_from_link(a)

        if not title or href in seen:
            continue

        card_text = card_text_from_link(a)
        rating, views, likes = extract_metrics(card_text)
        original_rank = extract_original_rank(card_text)

        seen.add(href)

        # 추출한 값이 없으면 None으로 남깁니다.
        # 다른 작품의 값을 가져오거나 추정하지 않습니다.
        like_rate = None
        if views is not None and likes is not None and views > 0:
            like_rate = likes / views * 100

        results.append({
            "원본 순위": original_rank,
            "작품명": title,
            "플랫폼": platform_name,
            "평점": rating,
            "조회수": views,
            "좋아요": likes,
            "좋아요율(%)": like_rate,
            "작품 링크": href,
        })

    return results


# =====================================================
# 플랫폼 데이터 수집
# =====================================================

def get_platform_data(platform_name, selected_period):
    base_url = URLS[platform_name][selected_period]

    try:
        results = []

        # 네이버시리즈는 페이지를 나눠서 최대 100개를 모읍니다.
        # 다른 플랫폼은 공개 페이지의 HTML에 있는 작품만 수집합니다.
        page_count = 5 if platform_name == "네이버시리즈" else 1

        for page in range(1, page_count + 1):
            url = (
                add_page_number(base_url, page)
                if platform_name == "네이버시리즈"
                else base_url
            )

            html = fetch_html(url)
            rows = parse_page(html, platform_name, url)
            results.extend(rows)

            if len(results) >= 100:
                break

        # 중복 작품 제거
        unique = {}
        for row in results:
            unique.setdefault(row["작품 링크"], row)

        results = list(unique.values())

        if not results:
            return [], "작품 목록을 읽지 못했습니다. 공개 페이지 구조를 확인해야 합니다."

        return results[:100], None

    except requests.exceptions.Timeout:
        return [], "사이트 응답 시간이 초과되었습니다."
    except requests.exceptions.HTTPError as e:
        return [], f"HTTP 오류: {e.response.status_code}"
    except requests.exceptions.RequestException:
        return [], "사이트에 연결할 수 없습니다."
    except Exception as e:
        return [], f"데이터 처리 오류: {e}"


# =====================================================
# 메인 화면
# =====================================================

st.title("📚 웹소설 통합 랭킹 TOP 100")

st.caption(
    f"기준 날짜: {YESTERDAY:%Y년 %m월 %d일} · "
    f"{platform} · {period} · {metric}"
)

st.info(
    "어제 날짜는 한국 시간 기준입니다. "
    "플랫폼이 과거 데이터를 제공하지 않으면 현재 공개 페이지의 지표를 "
    "어제의 지표로 간주할 수 없습니다."
)

platforms_to_fetch = (
    ["네이버시리즈", "카카오페이지", "문피아"]
    if platform == "전체 플랫폼"
    else [platform]
)

all_rows = []
errors = []

with st.spinner("작품 제목과 공개 지표를 확인하고 있습니다..."):
    for name in platforms_to_fetch:
        rows, error = get_platform_data(name, period)
        all_rows.extend(rows)

        if error:
            errors.append((name, error))


# =====================================================
# 순위 계산
# =====================================================

if metric == "평점순":
    metric_column = "평점"
else:
    metric_column = "좋아요율(%)"

df = pd.DataFrame(all_rows)

if not df.empty:
    # 선택한 지표가 실제로 확인된 작품만 순위에 포함합니다.
    df[metric_column] = pd.to_numeric(
        df[metric_column],
        errors="coerce",
    )

    ranked_df = df.dropna(subset=[metric_column]).copy()

    # 높은 평점 또는 높은 좋아요율이 위로 오도록 정렬합니다.
    ranked_df = ranked_df.sort_values(
        by=metric_column,
        ascending=False,
        kind="stable",
    )

    # 동점 작품의 순위를 동일하게 표시합니다.
    ranked_df["순위"] = (
        ranked_df[metric_column]
        .rank(method="min", ascending=False)
        .astype(int)
    )

    ranked_df = ranked_df.head(count).copy()

else:
    ranked_df = pd.DataFrame()


# =====================================================
# 결과 표시
# =====================================================

if errors:
    with st.expander("⚠️ 일부 플랫폼 조회 안내", expanded=True):
        for name, error in errors:
            st.warning(f"{name}: {error}")
            st.markdown(f"[공식 랭킹 페이지 열기]({URLS[name][period]})")

if ranked_df.empty:
    st.warning(
        f"선택한 기준인 '{metric}' 값이 공개 페이지에서 확인되는 작품이 없습니다. "
        "지표가 없는 작품에 임의의 점수를 부여하지 않았습니다."
    )

else:
    c1, c2, c3 = st.columns(3)

    c1.metric("지표 확인 작품", f"{len(ranked_df)}개")
    c2.metric("정렬 기준", metric)
    c3.metric("조회 기간", period)

    st.divider()

    display_df = ranked_df[
        [
            "순위",
            "작품명",
            "플랫폼",
            "평점",
            "조회수",
            "좋아요",
            "좋아요율(%)",
            "작품 링크",
        ]
    ].copy()

    display_df["조회수"] = display_df["조회수"].apply(
        lambda x: f"{x:,.0f}" if pd.notna(x) else "—"
    )

    display_df["좋아요"] = display_df["좋아요"].apply(
        lambda x: f"{x:,.0f}" if pd.notna(x) else "—"
    )

    display_df["평점"] = display_df["평점"].apply(
        lambda x: f"{x:.1f}" if pd.notna(x) else "—"
    )

    display_df["좋아요율(%)"] = display_df["좋아요율(%)"].apply(
        lambda x: f"{x:.2f}%" if pd.notna(x) else "—"
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=650,
        column_config={
            "작품 링크": st.column_config.LinkColumn(
                "작품 보기",
                display_text="바로가기 ↗",
            )
        },
    )

    st.caption(
        "평점순은 평점이 확인된 작품만, 좋아요율순은 좋아요와 조회수가 "
        "모두 확인된 작품만 정렬합니다. 플랫폼별 지표 정의는 다를 수 있습니다."
    )


# =====================================================
# 접을 수 있는 도움말
# =====================================================

with st.expander("순위 산정 기준"):
    st.markdown("""
    - **평점순:** 공개된 평점을 내림차순으로 정렬합니다.
    - **좋아요율순:** 좋아요 수 ÷ 조회수 × 100으로 계산합니다.
    - **지표 없음:** 임의의 점수를 만들지 않고 순위에서 제외합니다.
    - **전체 플랫폼:** 각 플랫폼에서 같은 지표가 확인된 작품을 함께 정렬합니다.
    - **과거 데이터:** 오늘 공개 페이지에서 읽은 값은 어제의 값이 아닐 수 있습니다.
    """)

    st.markdown(
        "[네이버시리즈 공식 랭킹](https://series.naver.com/novel/top100List.series) · "
        "[카카오페이지 공식 랭킹](https://page.kakao.com/landing/ranking/0) · "
        "[문피아 공식 랭킹](https://www.munpia.com/best/today)"
    )
