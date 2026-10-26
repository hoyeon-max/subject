
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urljoin

import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup


# ==================================================
# 웹소설 통합 랭킹 TOP 100
# 한국 시간 기준 어제 날짜 자동 계산
# ==================================================

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

# 플랫폼별 공식 랭킹 주소
RANKING_URLS = {
    "네이버시리즈": {
        "일간": "https://series.naver.com/novel/top100List.series?categoryCode=ALL&rankingTypeCode=DAILY",
        "주간": "https://series.naver.com/novel/top100List.series?categoryCode=ALL&rankingTypeCode=WEEKLY",
        "월간": "https://series.naver.com/novel/top100List.series?categoryCode=ALL&rankingTypeCode=MONTHLY",
    },
    "카카오페이지": {
        "일간": "https://page.kakao.com/landing/ranking/16/0?ranking_type=daily",
        "주간": "https://page.kakao.com/landing/ranking/16/0?ranking_type=weekly",
        "월간": "https://page.kakao.com/landing/ranking/16/0?ranking_type=monthly",
    },
    "문피아": {
        "일간": "https://www.munpia.com/best/today",
        "주간": "https://www.munpia.com/best/plsa.weekly",
        "월간": "https://www.munpia.com/best/plsa.monthly",
    },
}

HOME_URLS = {
    "네이버시리즈": "https://series.naver.com/novel/top100List.series",
    "카카오페이지": "https://page.kakao.com/landing/ranking/0",
    "문피아": "https://www.munpia.com/best/today",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}


# ==================================================
# 화면 디자인
# ==================================================

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
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: #eee0cd;
    border-radius: 12px;
}
a {
    text-decoration: none;
}
</style>
""", unsafe_allow_html=True)


# ==================================================
# 왼쪽 사이드바: 필요한 설정만 표시
# ==================================================

with st.sidebar:
    st.title("📚 웹소설 랭킹")

    with st.expander("⚙️ 조회 설정", expanded=True):
        platform = st.selectbox(
            "플랫폼",
            PLATFORMS,
        )

        period = st.radio(
            "기간",
            PERIODS,
            horizontal=True,
        )

        count = st.select_slider(
            "표시 작품 수",
            options=[10, 20, 50, 100],
            value=100,
            format_func=lambda n: f"TOP {n}",
        )

    st.caption(
        f"한국 시간 기준 어제: {YESTERDAY:%Y-%m-%d}"
    )

    refresh = st.button(
        "🔄 새로고침",
        use_container_width=True,
    )

    st.divider()

    st.caption("작품 제목을 누르면 해당 플랫폼으로 이동합니다.")


if refresh:
    st.cache_data.clear()
    st.rerun()


# ==================================================
# 웹페이지 가져오기
# ==================================================

@st.cache_data(ttl=900, show_spinner=False)
def fetch_html(url):
    """웹페이지 HTML을 가져옵니다."""
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


# ==================================================
# 작품 목록 추출
# ==================================================

def parse_ranking(html, platform_name, source_url):
    """
    공개 페이지에서 작품 링크를 추출합니다.

    순위가 별도 텍스트로 제공되지 않는 페이지에서는
    페이지에 나타나는 작품 순서를 이용합니다.
    메뉴나 일반 링크는 작품으로 취급하지 않습니다.
    """
    soup = BeautifulSoup(html, "html.parser")

    results = []
    seen = set()

    excluded_titles = {
        "로그인", "회원가입", "고객센터", "공지사항",
        "이용약관", "개인정보처리방침", "회사소개",
        "검색", "홈", "이벤트", "웹소설", "웹툰",
        "무료충전", "더보기", "랭킹", "전체",
    }

    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        link = urljoin(source_url, a["href"])

        if not title or len(title) < 2 or len(title) > 90:
            continue

        if title in excluded_titles:
            continue

        if any(word in title for word in excluded_titles):
            continue

        # 플랫폼별 작품 링크인지 확인합니다.
        if platform_name == "네이버시리즈":
            if "series.naver.com/novel/" not in link:
                continue

        elif platform_name == "카카오페이지":
            if "page.kakao.com" not in link:
                continue

            # 작품 상세 주소가 아닌 일반 페이지는 제외합니다.
            if "/content/" not in link and "/viewer/" not in link:
                continue

        elif platform_name == "문피아":
            if "munpia.com" not in link:
                continue

            if "/best/" in link or "/help/" in link:
                continue

        if link in seen:
            continue

        seen.add(link)

        # 주변 문구에서 실제 표시된 순위가 있으면 사용합니다.
        parent_text = (
            a.parent.get_text(" ", strip=True)
            if a.parent else ""
        )

        match = re.search(
            r"(?:^|\s)(100|[1-9]?\d)(?:위|\s)",
            parent_text,
        )

        results.append({
            "원본 순위": int(match.group(1)) if match else None,
            "작품명": title,
            "플랫폼": platform_name,
            "작품 링크": link,
        })

        if len(results) >= 100:
            break

    # 순위가 확인된 작품은 원래 순위순으로 정렬합니다.
    # 나머지는 페이지에서 나타난 순서를 유지합니다.
    ranked = [r for r in results if r["원본 순위"] is not None]
    unranked = [r for r in results if r["원본 순위"] is None]

    ranked.sort(key=lambda r: r["원본 순위"])

    # 원본 순위가 없는 항목에 가짜 순위를 붙이지 않습니다.
    return ranked + unranked


def get_ranking(platform_name, selected_period):
    """플랫폼별 공개 랭킹 페이지를 조회합니다."""
    url = RANKING_URLS[platform_name][selected_period]

    try:
        html = fetch_html(url)
        rows = parse_ranking(html, platform_name, url)

        if not rows:
            return [], (
                "작품 목록을 추출하지 못했습니다. "
                "사이트의 데이터 구조 또는 접근 방식 확인이 필요합니다."
            )

        return rows, None

    except requests.exceptions.Timeout:
        return [], "사이트 응답 시간이 초과되었습니다."

    except requests.exceptions.HTTPError as e:
        return [], f"HTTP 오류: {e.response.status_code}"

    except requests.exceptions.RequestException:
        return [], "사이트에 연결할 수 없습니다."

    except Exception as e:
        return [], f"데이터 처리 오류: {e}"


# ==================================================
# 메인 화면
# ==================================================

st.title("📚 웹소설 통합 랭킹 TOP 100")

st.caption(
    f"{YESTERDAY:%Y년 %m월 %d일} 기준 날짜 · "
    f"{platform} · {period}"
)

st.info(
    "날짜는 한국 시간 기준 어제로 자동 계산됩니다. "
    "단, 플랫폼이 과거 순위를 제공하지 않으면 현재 페이지에서 "
    "어제 당시 순위를 복원할 수는 없습니다."
)


# ==================================================
# 순위 조회 및 표시
# ==================================================

platforms_to_fetch = (
    ["네이버시리즈", "카카오페이지", "문피아"]
    if platform == "전체 플랫폼"
    else [platform]
)

all_rows = []
errors = []

with st.spinner("공개 랭킹을 확인하고 있습니다..."):
    for name in platforms_to_fetch:
        rows, error = get_ranking(name, period)

        all_rows.extend(rows)

        if error:
            errors.append((name, error))


# 수집 실패한 플랫폼은 공식 사이트 링크를 보여줍니다.
if errors:
    with st.expander("⚠️ 조회가 필요한 플랫폼", expanded=True):
        for name, error in errors:
            st.warning(f"{name}: {error}")
            st.markdown(
                f"[{name} 공식 사이트 열기]({HOME_URLS[name]})"
            )


if not all_rows:
    st.warning(
        "표시할 작품을 찾지 못했습니다. "
        "공식 사이트에 접속해 확인해 주세요."
    )

else:
    df = pd.DataFrame(all_rows)

    # 한 플랫폼에서는 원래 순위순으로 보여주고,
    # 전체 플랫폼에서는 각 플랫폼의 결과를 합쳐 보여줍니다.
    if platform != "전체 플랫폼":
        df = df.sort_values(
            by="원본 순위",
            na_position="last",
        )

    df = df.head(count).copy()

    # 요약 카드
    col1, col2, col3 = st.columns(3)

    col1.metric("표시 작품", f"{len(df)}개")
    col2.metric("플랫폼", f"{len(platforms_to_fetch)}개")
    col3.metric("조회 기간", period)

    st.divider()

    # 원래 순위가 없는 작품은 페이지상 위치를 임시 번호로 표시하지 않습니다.
    display_df = df[[
        "원본 순위",
        "작품명",
        "플랫폼",
        "작품 링크",
    ]].copy()

    display_df["원본 순위"] = display_df["원본 순위"].apply(
        lambda x: f"{int(x)}위" if pd.notna(x) else "순위 확인 필요"
    )

    display_df.columns = [
        "순위",
        "작품명",
        "플랫폼",
        "작품 링크",
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=650,
        column_config={
            "작품 링크": st.column_config.LinkColumn(
                "바로가기",
                display_text="작품 보기 ↗",
            )
        },
    )

    st.caption(
        "전체 플랫폼 보기는 각 사이트의 결과를 함께 표시합니다. "
        "서로 다른 플랫폼의 순위를 합산한 통합 순위는 아닙니다."
    )


# ==================================================
# 하단 도움말
# ==================================================

with st.expander("데이터 기준 및 안내"):
    st.markdown(
        """
        - **일간·주간·월간:** 선택한 플랫폼의 공개 랭킹 주소를 조회합니다.
        - **어제:** 한국 시간 기준으로 자동 계산합니다.
        - **TOP 100:** 실제로 추출할 수 있는 작품까지만 표시합니다.
        - **과거 순위:** 과거 순위 기록이 제공되지 않으면 복원할 수 없습니다.
        - **수집 오류:** 플랫폼의 페이지 구조 변경이나 동적 로딩 때문에 발생할 수 있습니다.
        """
    )
