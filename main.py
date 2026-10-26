
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urljoin

import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="웹소설 TOP 100",
    page_icon="📚",
    layout="wide",
)

KST = ZoneInfo("Asia/Seoul")
TODAY = datetime.now(KST).date()
YESTERDAY = TODAY - timedelta(days=1)

PLATFORMS = ["전체", "네이버시리즈", "카카오페이지", "문피아"]
PERIODS = ["일간", "주간", "월간"]

HOME_URLS = {
    "네이버시리즈": "https://series.naver.com/novel/top100List.series",
    "카카오페이지": "https://page.kakao.com/",
    "문피아": "https://www.munpia.com/best/today",
}

RANK_URLS = {
    "네이버시리즈": {
        "일간": "https://series.naver.com/novel/top100List.series?categoryCode=ALL&rankingTypeCode=DAILY",
        "주간": "https://series.naver.com/novel/top100List.series?categoryCode=ALL&rankingTypeCode=WEEKLY",
        "월간": "https://series.naver.com/novel/top100List.series?categoryCode=ALL&rankingTypeCode=MONTHLY",
    },
    "카카오페이지": {
        "일간": "https://page.kakao.com/",
        "주간": "https://page.kakao.com/",
        "월간": "https://page.kakao.com/",
    },
    "문피아": {
        "일간": "https://www.munpia.com/best/today",
        "주간": "https://www.munpia.com/best/today",
        "월간": "https://www.munpia.com/best/today",
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}


# --------------------------------------------------
# 화면 디자인
# --------------------------------------------------

st.markdown(
    """
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
        padding: 12px;
        border-radius: 12px;
        border: 1px solid #f0d9b3;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: #eee0cd;
        border-radius: 12px;
    }

    .small-note {
        color: #8a7b69;
        font-size: 13px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# 사이드바: 조회 설정을 한곳에 모으기
# --------------------------------------------------

with st.sidebar:
    st.title("📚 웹소설 랭킹")
    st.caption("간단하게 원하는 순위를 찾아보세요.")

    with st.expander("⚙️ 조회 설정", expanded=True):
        platform = st.selectbox(
            "플랫폼",
            PLATFORMS,
        )

        period = st.radio(
            "순위 기간",
            PERIODS,
            horizontal=True,
        )

        count = st.select_slider(
            "표시 개수",
            options=[10, 20, 50, 100],
            value=100,
            format_func=lambda x: f"TOP {x}",
        )

        st.caption(
            f"조회 기준 날짜: {YESTERDAY.strftime('%Y-%m-%d')} (한국 시간)"
        )

    refresh = st.button(
        "🔄 새로고침",
        use_container_width=True,
    )

    st.divider()
    st.caption("공개된 랭킹 정보만 조회합니다.")
    st.caption("플랫폼별 집계 기준은 서로 다를 수 있습니다.")

if refresh:
    st.cache_data.clear()
    st.rerun()


# --------------------------------------------------
# 웹페이지 가져오기
# --------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_html(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


# --------------------------------------------------
# 작품 링크와 제목 추출
# --------------------------------------------------

def parse_ranking(html, platform_name, source_url):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()

    excluded = [
        "로그인", "회원가입", "고객센터", "이용약관",
        "개인정보", "공지사항", "이벤트", "검색",
        "무료충전", "회사소개", "웹툰",
    ]

    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        link = urljoin(source_url, a["href"])

        if not title or len(title) < 2 or len(title) > 100:
            continue

        if any(word in title for word in excluded):
            continue

        if link.rstrip("/") == source_url.rstrip("/"):
            continue

        # 플랫폼별 도메인을 확인해 엉뚱한 링크를 제외합니다.
        if platform_name == "네이버시리즈":
            if "series.naver.com/novel/" not in link:
                continue
        elif platform_name == "카카오페이지":
            if "page.kakao.com" not in link:
                continue
            if link.rstrip("/") == "https://page.kakao.com":
                continue
        elif platform_name == "문피아":
            if "munpia.com" not in link or "/best/" in link:
                continue

        if link in seen:
            continue
        seen.add(link)

        # 주변 문구에서 순위를 명확하게 찾을 수 있을 때만 표시합니다.
        parent_text = a.parent.get_text(" ", strip=True) if a.parent else ""
        match = re.search(r"(?:^|\s)(100|[1-9]?\d)(?:위|\s)", parent_text)
        rank = int(match.group(1)) if match else None

        results.append({
            "순위": rank,
            "작품명": title,
            "플랫폼": platform_name,
            "링크": link,
        })

    # 확인된 원래 순위를 우선 표시합니다.
    results.sort(
        key=lambda x: (
            x["순위"] is None,
            x["순위"] if x["순위"] is not None else 999,
        )
    )

    return results[:100]


def get_ranking(platform_name, selected_period):
    url = RANK_URLS[platform_name][selected_period]

    try:
        html = fetch_html(url)
        results = parse_ranking(html, platform_name, url)

        if not results:
            return [], (
                "작품 목록을 가져오지 못했습니다. "
                "사이트 구조가 바뀌었거나 별도의 데이터 요청이 필요할 수 있습니다."
            )

        return results, None

    except requests.exceptions.Timeout:
        return [], "사이트 응답 시간이 초과되었습니다."
    except requests.exceptions.HTTPError as e:
        return [], f"사이트 응답 오류: HTTP {e.response.status_code}"
    except requests.exceptions.RequestException:
        return [], "사이트에 연결할 수 없습니다."
    except Exception:
        return [], "순위 데이터를 처리하지 못했습니다."


# --------------------------------------------------
# 메인 화면: 순위에 집중
# --------------------------------------------------

st.title("📚 웹소설 TOP 100")

st.caption(
    f"기준 날짜 {YESTERDAY.strftime('%Y년 %m월 %d일')} · "
    f"{platform} · {period}"
)

st.warning(
    "어제 날짜는 한국 시간으로 자동 계산됩니다. "
    "단, 사이트가 현재 순위만 제공하면 어제 당시의 순위를 복원할 수 없습니다."
)

platforms_to_fetch = (
    ["네이버시리즈", "카카오페이지", "문피아"]
    if platform == "전체"
    else [platform]
)

all_rows = []
errors = []

with st.spinner("순위를 확인하고 있습니다..."):
    for name in platforms_to_fetch:
        rows, error = get_ranking(name, period)
        all_rows.extend(rows)

        if error:
            errors.append((name, error))

if errors:
    with st.expander("⚠️ 일부 플랫폼의 조회 문제", expanded=True):
        for name, error in errors:
            st.write(f"**{name}** — {error}")
            st.link_button(
                f"{name} 공식 사이트 열기",
                HOME_URLS[name],
                key=f"home_{name}",
            )

if not all_rows:
    st.info(
        "표시할 순위가 없습니다. 공식 사이트에서 확인해 주세요. "
        "사이트별 실제 랭킹 주소와 데이터 구조를 연결해야 정상적으로 표시됩니다."
    )

else:
    df = pd.DataFrame(all_rows).head(count).copy()

    # 요약 정보
    col1, col2 = st.columns(2)
    col1.metric("표시 작품", f"{len(df)}개")
    col2.metric("조회 플랫폼", f"{len(platforms_to_fetch)}개")

    st.divider()

    # 표를 사용해 많은 작품도 한눈에 볼 수 있게 합니다.
    display_df = df.rename(columns={
        "순위": "원래 순위",
        "작품명": "작품명",
        "플랫폼": "플랫폼",
        "링크": "작품 링크",
    })

    display_df["원래 순위"] = display_df["원래 순위"].apply(
        lambda x: f"{int(x)}위" if pd.notna(x) else "미확인"
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "작품 링크": st.column_config.LinkColumn(
                "작품 바로가기",
                display_text="작품 보기 ↗",
            )
        },
    )

    st.caption(
        "전체 보기는 각 플랫폼의 결과를 모아 표시합니다. "
        "플랫폼별 순위를 합산해 새 순위를 만든 것은 아닙니다."
    )

st.divider()

with st.expander("ℹ️ 순위 데이터 안내"):
    st.write(
        "이 앱은 공개 웹페이지에서 제목과 링크를 추출하는 기본 기능을 제공합니다. "
        "사이트마다 순위 표시 방식이 달라 TOP 100이 정확히 수집된다고 보장할 수 없습니다."
    )
    st.write(
        "현재 카카오페이지 주소는 실제 일간·주간·월간 랭킹 주소가 확인된 상태가 아니며, "
        "문피아 주소도 기간별 순위를 보장하지 않습니다. "
        "정확한 순위를 표시하려면 각 플랫폼의 실제 랭킹 데이터 연결이 필요합니다."
    )
