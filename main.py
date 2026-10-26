
# ============================================================
# 웹소설 통합 랭킹 대시보드
# 지원 플랫폼: 네이버시리즈, 카카오페이지, 문피아
# 기능: 일간 / 주간 / 월간 / 플랫폼 전체 및 개별 보기
#
# 초보자 안내:
# 1. 한국 시간 기준 어제 날짜를 자동으로 계산합니다.
# 2. 공개된 웹페이지에서 순위 데이터를 가져옵니다.
# 3. 실제로 수집되지 않은 작품은 임의로 만들어 넣지 않습니다.
# 4. 사이트의 HTML 구조가 바뀌면 수집 기능을 수정해야 할 수 있습니다.
# ============================================================

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urljoin

import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup


# ------------------------------------------------------------
# 1. 기본 설정
# ------------------------------------------------------------

st.set_page_config(
    page_title="웹소설 통합 랭킹 TOP 100",
    page_icon="📚",
    layout="wide",
)

KST = ZoneInfo("Asia/Seoul")

# 서버의 시간대와 관계없이 한국 시간으로 어제를 계산합니다.
KOREA_TODAY = datetime.now(KST).date()
YESTERDAY = KOREA_TODAY - timedelta(days=1)

PLATFORMS = [
    "전체 플랫폼",
    "네이버시리즈",
    "카카오페이지",
    "문피아",
]

PERIODS = ["일간", "주간", "월간"]

# 공식 사이트 주소
PLATFORM_HOME = {
    "네이버시리즈": "https://series.naver.com/novel/top100List.series",
    "카카오페이지": "https://page.kakao.com/",
    "문피아": "https://www.munpia.com/best/today",
}

# 플랫폼별 공개 랭킹 주소입니다.
# 사이트 개편에 따라 주소 또는 집계 방식이 바뀔 수 있습니다.
RANKING_URLS = {
    "네이버시리즈": {
        "일간": (
            "https://series.naver.com/novel/top100List.series"
            "?categoryCode=ALL&rankingTypeCode=DAILY"
        ),
        "주간": (
            "https://series.naver.com/novel/top100List.series"
            "?categoryCode=ALL&rankingTypeCode=WEEKLY"
        ),
        "월간": (
            "https://series.naver.com/novel/top100List.series"
            "?categoryCode=ALL&rankingTypeCode=MONTHLY"
        ),
    },
    "카카오페이지": {
        # 아래 주소는 공식 사이트 진입 주소입니다.
        # 실제 랭킹을 가져오려면 사이트가 공개하는 랭킹 페이지를
        # 확인한 뒤 해당 주소로 변경해야 할 수 있습니다.
        "일간": "https://page.kakao.com/",
        "주간": "https://page.kakao.com/",
        "월간": "https://page.kakao.com/",
    },
    "문피아": {
        # 문피아에서 확인 가능한 공개 랭킹 페이지
        "일간": "https://www.munpia.com/best/today",
        "주간": "https://www.munpia.com/best/today",
        "월간": "https://www.munpia.com/best/today",
    },
}


# ------------------------------------------------------------
# 2. 화면 디자인
# ------------------------------------------------------------

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(180deg, #fffaf0 0%, #fffdf8 100%);
        color: #3d3429;
    }

    .main-title {
        font-size: 36px;
        font-weight: 850;
        color: #593d27;
        letter-spacing: -1.5px;
    }

    .sub-title {
        color: #8b7355;
        font-size: 16px;
        line-height: 1.8;
    }

    .info-card {
        background: #fff1d6;
        border: 1px solid #f1d6a6;
        border-radius: 15px;
        padding: 18px;
        margin: 8px 0;
    }

    .rank-number {
        font-size: 23px;
        font-weight: 800;
        color: #9b6b25;
        min-width: 42px;
    }

    .rank-title {
        font-size: 17px;
        font-weight: 750;
        color: #443225;
    }

    .rank-platform {
        font-size: 13px;
        color: #8c7b69;
    }

    div[data-testid="stMetric"] {
        background: #fff1d6;
        border: 1px solid #f1d6a6;
        border-radius: 14px;
        padding: 15px;
    }

    .stButton button {
        border-radius: 12px;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-title">📚 웹소설 통합 랭킹</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="sub-title">
    네이버시리즈 · 카카오페이지 · 문피아의 공개 랭킹을 한곳에서 확인하세요.<br>
    일간, 주간, 월간 순위를 선택하고 최대 TOP 100까지 살펴볼 수 있습니다.
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

# ------------------------------------------------------------
# 3. 날짜 안내
# ------------------------------------------------------------

st.markdown(
    f"""
    <div class="info-card">
        <b>🗓️ 한국 시간 기준</b><br>
        오늘: {KOREA_TODAY.strftime("%Y-%m-%d")}<br>
        자동 계산된 어제: <b>{YESTERDAY.strftime("%Y-%m-%d")}</b>
    </div>
    """,
    unsafe_allow_html=True,
)

st.warning(
    "주의: 어제 날짜는 한국 시간으로 자동 계산됩니다. "
    "하지만 공개 랭킹 페이지가 현재 순위만 제공한다면, "
    "그 데이터를 어제 당시의 순위라고 볼 수는 없습니다. "
    "정확한 과거 순위는 플랫폼의 과거 데이터 제공 또는 별도 기록이 필요합니다."
)


# ------------------------------------------------------------
# 4. 웹페이지 가져오기
# ------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_html(url):
    """
    웹페이지 HTML을 가져옵니다.
    30분 동안 결과를 저장해 반복 요청을 줄입니다.
    """
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


# ------------------------------------------------------------
# 5. 공개 HTML에서 작품 링크 찾기
# ------------------------------------------------------------

def parse_ranking_html(html, platform, source_url):
    """
    HTML에서 작품 제목과 링크를 추출합니다.

    주의:
    사이트별 HTML이 다르기 때문에 일반적인 링크 추출 방식만으로
    실제 순위를 100개 정확히 복원할 수 있다고 보장할 수 없습니다.
    숫자 순위를 확실하게 확인할 수 없는 링크에는 순위를 붙이지 않습니다.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()

    # 메뉴, 로그인, 광고 등 일반적인 링크를 일부 제외합니다.
    excluded_words = [
        "로그인", "회원가입", "고객센터", "이용약관",
        "개인정보", "회사소개", "공지사항", "이벤트",
        "웹툰", "홈", "검색", "무료충전", "충전소",
    ]

    # 페이지 내 링크 중 작품 제목 후보를 찾습니다.
    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        href = urljoin(source_url, a["href"])

        # 빈 제목이나 지나치게 긴 링크 문구를 제외합니다.
        if not title or len(title) < 2 or len(title) > 100:
            continue

        # 메뉴나 공통 링크는 제외합니다.
        if any(word in title for word in excluded_words):
            continue

        # 페이지 이동 및 외부 사이트 링크 중 작품 링크가 아닌 항목을 줄입니다.
        if href.rstrip("/") == source_url.rstrip("/"):
            continue

        if platform == "네이버시리즈":
            if "series.naver.com/novel/" not in href:
                continue
        elif platform == "문피아":
            if "munpia.com" not in href:
                continue
            if "/best/" in href or "/help/" in href:
                continue
        elif platform == "카카오페이지":
            # 카카오페이지의 홈 화면 링크를 작품으로 오인하지 않습니다.
            if "page.kakao.com" not in href:
                continue
            if href.rstrip("/") == "https://page.kakao.com":
                continue

        # 같은 작품 링크 중복 방지
        if href in seen:
            continue
        seen.add(href)

        # 링크 앞뒤 텍스트에서 순위를 확실히 확인할 수 있는 경우만 사용
        parent_text = a.parent.get_text(" ", strip=True) if a.parent else ""
        rank_match = re.search(
            r"(?:^|\s)(100|[1-9]?\d)(?:위|\s)",
            parent_text,
        )

        rank = int(rank_match.group(1)) if rank_match else None

        results.append(
            {
                "순위": rank,
                "작품명": title,
                "플랫폼": platform,
                "작품 링크": href,
                "순위 확인": "확인" if rank is not None else "미확인",
            }
        )

    # 실제 순위 번호를 확인할 수 있는 항목을 우선 배치합니다.
    results.sort(
        key=lambda x: (
            x["순위"] is None,
            x["순위"] if x["순위"] is not None else 999,
        )
    )

    # 최대 100개까지만 반환합니다.
    return results[:100]


# ------------------------------------------------------------
# 6. 플랫폼별 순위 수집
# ------------------------------------------------------------

def get_platform_ranking(platform, period):
    """
    선택한 플랫폼의 공개 페이지를 가져와 작품 목록을 만듭니다.
    실패한 경우에는 오류 메시지를 반환합니다.
    """
    url = RANKING_URLS[platform][period]

    try:
        html = fetch_html(url)
        results = parse_ranking_html(html, platform, url)

        if not results:
            return [], (
                f"{platform}: 작품 목록을 추출하지 못했습니다. "
                "페이지 구조가 바뀌었거나 JavaScript로 렌더링되는 페이지일 수 있습니다."
            )

        return results, None

    except requests.exceptions.Timeout:
        return [], f"{platform}: 응답 시간이 초과되었습니다."

    except requests.exceptions.HTTPError as e:
        return [], f"{platform}: HTTP 오류가 발생했습니다 ({e.response.status_code})."

    except requests.exceptions.RequestException as e:
        return [], f"{platform}: 네트워크 요청에 실패했습니다 ({e})."

    except Exception as e:
        return [], f"{platform}: 데이터를 처리하지 못했습니다 ({e})."


# ------------------------------------------------------------
# 7. 검색 조건
# ------------------------------------------------------------

st.subheader("🔎 순위 조회")

col1, col2, col3 = st.columns([1.2, 1, 1])

with col1:
    selected_platform = st.selectbox(
        "플랫폼",
        PLATFORMS,
        index=0,
    )

with col2:
    selected_period = st.selectbox(
        "순위 유형",
        PERIODS,
        index=0,
    )

with col3:
    display_count = st.selectbox(
        "표시 개수",
        [10, 20, 50, 100],
        index=3,
        format_func=lambda x: f"TOP {x}",
    )

# 조회 버튼으로 다시 수집할 수 있도록 구성합니다.
if st.button("🔄 순위 새로 조회", use_container_width=True):
    st.cache_data.clear()
    st.rerun()


# ------------------------------------------------------------
# 8. 플랫폼별 순위 가져오기
# ------------------------------------------------------------

selected_platforms = (
    ["네이버시리즈", "카카오페이지", "문피아"]
    if selected_platform == "전체 플랫폼"
    else [selected_platform]
)

all_results = []
errors = []

with st.spinner("공개 랭킹 페이지에서 데이터를 확인하고 있습니다..."):
    for platform in selected_platforms:
        items, error = get_platform_ranking(
            platform,
            selected_period,
        )

        if error:
            errors.append(error)

        all_results.extend(items)


# ------------------------------------------------------------
# 9. 결과 표시
# ------------------------------------------------------------

st.divider()

st.subheader(
    f"🏆 {selected_platform} · {selected_period} TOP {display_count}"
)

if errors:
    with st.expander("⚠️ 데이터를 가져오지 못한 플랫폼 확인", expanded=True):
        for error in errors:
            st.warning(error)

        st.markdown("#### 공식 사이트에서 직접 확인")
        for platform in selected_platforms:
            st.markdown(
                f"- [{platform} 공식 랭킹 페이지]({PLATFORM_HOME[platform]})"
            )

if not all_results:
    st.info(
        "현재 공개 페이지에서 표시할 수 있는 순위 데이터를 찾지 못했습니다. "
        "공식 사이트 링크를 이용하거나 페이지 구조에 맞는 전용 수집기를 연결해 주세요."
    )

else:
    df = pd.DataFrame(all_results)

    # 플랫폼별 원래 순위를 합산하거나 임의로 새로운 순위를 만들지 않습니다.
    # 원래 순위가 확인되지 않는 항목은 '미확인'으로 표시합니다.
    df["표시 순위"] = df["순위"].apply(
        lambda x: f"{int(x)}위" if pd.notna(x) else "미확인"
    )

    # 사용자가 원하는 TOP 개수만큼 표시합니다.
    df = df.head(display_count).copy()

    # 상단 요약 카드
    metric1, metric2, metric3 = st.columns(3)

    with metric1:
        st.metric("표시 작품 수", f"{len(df):,}개")

    with metric2:
        st.metric("조회 유형", selected_period)

    with metric3:
        st.metric("플랫폼 수", f"{len(selected_platforms)}개")

    # 작품 목록
    for _, row in df.iterrows():
        rank_text = row["표시 순위"]
        title = row["작품명"]
        platform = row["플랫폼"]
        link = row["작품 링크"]
        verified = row["순위 확인"]

        with st.container(border=True):
            left, right = st.columns([5, 1])

            with left:
                st.markdown(
                    f"### {rank_text} · {title}"
                )
                st.caption(
                    f"{platform} · 원래 순위 {verified}"
                )

            with right:
                st.link_button(
                    "작품 보기 ↗",
                    link,
                    use_container_width=True,
                )

    st.caption(
        "참고: 전체 플랫폼 보기에서는 각 플랫폼의 작품을 모아 보여줍니다. "
        "플랫폼마다 집계 기준이 다르므로 서로 다른 플랫폼의 순위를 "
        "단순 비교하거나 하나의 통합 순위로 해석하지 마세요."
    )


# ------------------------------------------------------------
# 10. 하단 안내
# ------------------------------------------------------------

st.divider()

st.markdown("### 📌 이용 안내")

st.markdown(
    """
    - **일간 / 주간 / 월간:** 선택한 플랫폼의 공개 랭킹 페이지를 조회합니다.
    - **어제 날짜:** 한국 시간 기준으로 자동 계산합니다.
    - **전체 플랫폼:** 세 플랫폼의 수집 결과를 함께 표시합니다.
    - **TOP 100:** 실제로 추출할 수 있는 항목만 표시합니다.
    - **순위 미확인:** 작품 링크는 찾았지만 원래 순위 번호를 확인하지 못한 항목입니다.
    - **과거 순위:** 플랫폼이 과거 기록을 제공하지 않으면 어제 당시 순위를 복원할 수 없습니다.
    - **수집 오류:** 페이지 변경, 로그인 요구, JavaScript 렌더링 또는 네트워크 제한으로 발생할 수 있습니다.
    """
)

st.caption(
    f"마지막 화면 기준 날짜: {YESTERDAY.strftime('%Y년 %m월 %d일')} "
    "| 시간대: Asia/Seoul"
)
