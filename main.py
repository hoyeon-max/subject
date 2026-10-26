
import re
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urljoin, urlparse

import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup


# =========================================================
# 웹소설 통합 랭킹 TOP 100
# =========================================================

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

# 플랫폼별 공개 랭킹 페이지
RANKING_URLS = {
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

# 작품 제목으로 취급하지 않을 메뉴 및 이벤트 문구
EXCLUDED_TITLES = {
    "타임딜",
    "매일10시무료",
    "무료",
    "무료충전",
    "무료이용권",
    "프리패스",
    "인기 단행본",
    "TOP 100",
    "웹소설",
    "웹툰",
    "로그인",
    "회원가입",
    "고객센터",
    "공지사항",
    "이벤트",
    "검색",
    "홈",
    "랭킹",
    "전체",
    "더보기",
    "이용약관",
    "개인정보처리방침",
    "회사소개",
    "오늘의 베스트",
    "주간 베스트",
    "월간 베스트",
}

# 제목에 다음과 같은 메뉴 문구가 포함된 경우도 제외합니다.
EXCLUDED_PREFIXES = (
    "타임딜",
    "매일10시무료",
    "무료충전",
    "로그인",
    "회원가입",
)


# =========================================================
# 화면 디자인
# =========================================================

st.markdown("""
<style>
.stApp {
    background: #fffaf2;
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


# =========================================================
# 사이드바 설정
# =========================================================

with st.sidebar:
    st.title("📚 웹소설 랭킹")

    with st.expander("⚙️ 조회 설정", expanded=True):
        platform = st.selectbox("플랫폼", PLATFORMS)
        period = st.radio("기간", PERIODS, horizontal=True)

        count = st.select_slider(
            "표시 개수",
            options=[10, 20, 50, 100],
            value=100,
            format_func=lambda n: f"TOP {n}",
        )

    st.caption(f"한국 시간 기준 어제: {YESTERDAY:%Y-%m-%d}")

    refresh = st.button("🔄 새로고침", use_container_width=True)

    st.divider()
    st.caption("검증된 작품 제목만 표시합니다.")


if refresh:
    st.cache_data.clear()
    st.rerun()


# =========================================================
# 웹페이지 요청
# =========================================================

@st.cache_data(ttl=900, show_spinner=False)
def fetch_html(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


# =========================================================
# 제목 정리 및 검증
# =========================================================

def clean_title(title):
    """제목의 공백과 불필요한 문자를 정리합니다."""
    if not title:
        return ""

    title = re.sub(r"\s+", " ", title).strip()
    title = title.replace("\u200b", "").replace("\ufeff", "")
    title = title.strip(" |·•\n\t")

    return title


def is_valid_title(title):
    """
    제목이 실제 작품명 후보인지 확인합니다.
    메뉴와 이벤트 문구는 작품으로 등록하지 않습니다.
    """
    title = clean_title(title)

    if len(title) < 2 or len(title) > 100:
        return False

    if title in EXCLUDED_TITLES:
        return False

    if any(title.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return False

    if title.lower().startswith(("http://", "https://", "javascript:")):
        return False

    # 메뉴 이름만 조합된 제목은 제외합니다.
    if title in {"일간", "주간", "월간", "실시간", "무료", "유료"}:
        return False

    return True


def get_title_from_link(a):
    """
    링크 안의 텍스트를 먼저 확인하고,
    없으면 제목 속성이나 이미지 대체 텍스트를 확인합니다.
    """
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

        if is_valid_title(candidate):
            return candidate

    return ""


def get_rank_from_text(text):
    """원본 페이지의 텍스트에서 명시적인 순위만 추출합니다."""
    if not text:
        return None

    patterns = [
        r"(?:^|\s)(100|[1-9]?\d)\s*위(?:\s|$)",
        r"^\s*(100|[1-9]?\d)\s*$",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            rank = int(match.group(1))
            if 1 <= rank <= 100:
                return rank

    return None


# =========================================================
# 네이버시리즈 작품 추출
# =========================================================

def parse_naver(soup, source_url):
    results = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(source_url, a["href"])
        parsed = urlparse(href)

        # 네이버시리즈 웹소설 작품 상세 링크만 허용합니다.
        if parsed.netloc not in {
            "series.naver.com",
            "m.series.naver.com",
        }:
            continue

        if not re.search(r"/novel/(?:detail|content)", parsed.path):
            continue

        title = get_title_from_link(a)

        if not title or href in seen:
            continue

        # 부모 영역에서 원본 순위가 있는지 확인합니다.
        parent = a
        rank = None

        for _ in range(5):
            if parent.parent is None:
                break

            parent = parent.parent
            rank = get_rank_from_text(
                parent.get_text(" ", strip=True)[:250]
            )

            if rank is not None:
                break

        seen.add(href)

        results.append({
            "순위": rank,
            "작품명": title,
            "플랫폼": "네이버시리즈",
            "작품 링크": href,
        })

    return deduplicate_results(results)


# =========================================================
# 카카오페이지 작품 추출
# =========================================================

def parse_kakao(soup, source_url):
    results = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(source_url, a["href"])
        parsed = urlparse(href)

        if parsed.netloc != "page.kakao.com":
            continue

        # 실제 작품 상세 페이지에 해당하는 링크만 허용합니다.
        match = re.search(r"/content/(\d+)", parsed.path)

        if not match:
            continue

        title = get_title_from_link(a)

        if not title or href in seen:
            continue

        seen.add(href)

        parent = a.parent
        rank = None

        for _ in range(4):
            if parent is None:
                break

            rank = get_rank_from_text(
                parent.get_text(" ", strip=True)[:250]
            )

            if rank is not None:
                break

            parent = parent.parent

        results.append({
            "순위": rank,
            "작품명": title,
            "플랫폼": "카카오페이지",
            "작품 링크": href,
        })

    return deduplicate_results(results)


# =========================================================
# 문피아 작품 추출
# =========================================================

def parse_munpia(soup, source_url):
    results = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(source_url, a["href"])
        parsed = urlparse(href)

        if parsed.netloc not in {"www.munpia.com", "munpia.com"}:
            continue

        # 베스트 메뉴나 일반 페이지 링크는 제외합니다.
        if "/novel/" not in parsed.path:
            continue

        title = get_title_from_link(a)

        if not title or href in seen:
            continue

        seen.add(href)

        parent = a.parent
        rank = None

        for _ in range(5):
            if parent is None:
                break

            rank = get_rank_from_text(
                parent.get_text(" ", strip=True)[:300]
            )

            if rank is not None:
                break

            parent = parent.parent

        results.append({
            "순위": rank,
            "작품명": title,
            "플랫폼": "문피아",
            "작품 링크": href,
        })

    return deduplicate_results(results)


# =========================================================
# 중복 작품 제거
# =========================================================

def deduplicate_results(results):
    """같은 작품 링크가 여러 번 나오면 하나만 남깁니다."""
    output = []
    seen = set()

    for row in results:
        link = row["작품 링크"]

        if link in seen:
            continue

        if not is_valid_title(row["작품명"]):
            continue

        seen.add(link)
        output.append(row)

    # 원본 순위가 확인된 항목을 먼저 표시합니다.
    ranked = [x for x in output if x["순위"] is not None]
    unranked = [x for x in output if x["순위"] is None]

    ranked.sort(key=lambda x: x["순위"])

    return ranked + unranked


# =========================================================
# 플랫폼별 조회
# =========================================================

def get_ranking(platform_name, selected_period):
    url = RANKING_URLS[platform_name][selected_period]

    try:
        html = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        if platform_name == "네이버시리즈":
            rows = parse_naver(soup, url)

        elif platform_name == "카카오페이지":
            rows = parse_kakao(soup, url)

        elif platform_name == "문피아":
            rows = parse_munpia(soup, url)

        else:
            rows = []

        if not rows:
            return [], (
                "실제 작품 상세 링크를 확인하지 못했습니다. "
                "페이지가 JavaScript로 렌더링되거나 구조가 바뀌었을 수 있습니다."
            )

        return rows[:100], None

    except requests.exceptions.Timeout:
        return [], "사이트 응답 시간이 초과되었습니다."

    except requests.exceptions.HTTPError as e:
        return [], f"HTTP 오류: {e.response.status_code}"

    except requests.exceptions.RequestException:
        return [], "사이트에 연결할 수 없습니다."

    except Exception as e:
        return [], f"데이터 처리 오류: {e}"


# =========================================================
# 메인 화면
# =========================================================

st.title("📚 웹소설 통합 랭킹 TOP 100")

st.caption(
    f"한국 시간 기준 날짜: {YESTERDAY:%Y년 %m월 %d일} · "
    f"{platform} · {period}"
)

st.info(
    "날짜는 한국 시간 기준 어제로 계산합니다. "
    "단, 현재 페이지에 표시되는 순위가 어제의 순위라는 뜻은 아닙니다."
)

platforms_to_fetch = (
    ["네이버시리즈", "카카오페이지", "문피아"]
    if platform == "전체 플랫폼"
    else [platform]
)

all_rows = []
errors = []

with st.spinner("실제 작품 제목과 링크를 확인하고 있습니다..."):
    for name in platforms_to_fetch:
        rows, error = get_ranking(name, period)
        all_rows.extend(rows)

        if error:
            errors.append((name, error))


# =========================================================
# 결과 출력
# =========================================================

if errors:
    with st.expander("⚠️ 조회 상태 및 공식 사이트", expanded=True):
        for name, error in errors:
            st.warning(f"{name}: {error}")

            st.markdown(
                f"[{name} 공식 랭킹 페이지 열기]({RANKING_URLS[name][period]})"
            )

if not all_rows:
    st.warning(
        "표시할 작품을 확인하지 못했습니다. "
        "잘못된 제목을 임의로 표시하지 않았습니다."
    )

else:
    df = pd.DataFrame(all_rows)

    # 같은 플랫폼 내에서는 원본 순위가 확인된 작품을 먼저 표시합니다.
    # 전체 플랫폼에서는 플랫폼별 원래 순위를 그대로 보존합니다.
    if platform != "전체 플랫폼":
        df = df.sort_values(
            "순위",
            na_position="last",
        )

    df = df.head(count).copy()

    col1, col2, col3 = st.columns(3)
    col1.metric("확인한 작품", f"{len(df)}개")
    col2.metric("플랫폼", f"{len(platforms_to_fetch)}개")
    col3.metric("기간", period)

    st.divider()

    # 순위 번호를 확인하지 못한 작품에 가짜 순위를 부여하지 않습니다.
    display_df = df.copy()

    display_df["순위"] = display_df["순위"].apply(
        lambda x: f"{int(x)}위" if pd.notna(x) else "확인 필요"
    )

    display_df = display_df[
        ["순위", "작품명", "플랫폼", "작품 링크"]
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=650,
        column_config={
            "작품 링크": st.column_config.LinkColumn(
                "작품 바로가기",
                display_text="작품 보기 ↗",
            )
        },
    )

    st.caption(
        "전체 플랫폼은 각 플랫폼의 순위를 함께 보여줍니다. "
        "서로 다른 플랫폼의 순위를 합산해 새 순위를 만들지는 않습니다."
    )


# =========================================================
# 접어서 볼 수 있는 안내
# =========================================================

with st.expander("데이터 수집 안내"):
    st.markdown(
        """
        - 메뉴·이벤트 문구는 작품명 후보에서 제외합니다.
        - 작품 상세 페이지 주소가 확인되는 링크만 사용합니다.
        - 순위 번호가 확인되지 않으면 임의의 순위를 붙이지 않습니다.
        - 사이트의 JavaScript 렌더링이나 접근 제한으로 수집이 실패할 수 있습니다.
        - 과거 날짜의 정확한 순위는 별도 과거 기록이 필요합니다.
        """
    )
