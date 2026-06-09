import streamlit as st
import pandas as pd
import folium
import plotly.express as px
from streamlit_folium import st_folium
from pathlib import Path

from api import fetch_all_stations
from utils import preprocess, search_stations, filter_available, sort_stations

CSV_PATH = Path("data/bike_latest.csv")
TIMESTAMP_PATH = Path("data/last_updated.txt")

_STATUS_COLOR = {
    "🟢 충분": "#28a745",
    "🟡 보통": "#ffc107",
    "🟠 부족": "#fd7e14",
    "🔴 없음": "#dc3545",
}
_STATUS_ORDER = ["🟢 충분", "🟡 보통", "🟠 부족", "🔴 없음"]

_SEOUL_GU = [
    "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구",
    "성북구", "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구",
    "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구", "관악구",
    "서초구", "강남구", "송파구", "강동구",
]


def _extract_gu(name: str) -> str:
    for gu in _SEOUL_GU:
        if gu in str(name):
            return gu
    return "기타"

st.set_page_config(page_title="따릉이 Now", page_icon="🚲", layout="wide")


# ── 데이터 로딩 ──────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    if CSV_PATH.exists():
        df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
        return df
    df = fetch_all_stations()
    return preprocess(df)


def get_last_updated() -> str:
    if TIMESTAMP_PATH.exists():
        return TIMESTAMP_PATH.read_text(encoding="utf-8").strip()
    return "알 수 없음"


# ── 사이드바 ──────────────────────────────────────────────────
with st.sidebar:
    st.title("🚲 따릉이 Now")
    st.caption(f"마지막 업데이트: {get_last_updated()}")

    if st.button("🔄 새로고침"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    page = st.radio("메뉴", ["EDA 현황 분석", "실시간 대여소 찾기", "지도에서 보기", "빠른 추천"])
    st.divider()

    keyword = st.text_input("🔍 대여소명 검색", placeholder="예: 홍대, 강남, 여의도")
    only_available = st.checkbox("대여 가능한 대여소만 보기", value=True)
    sort_criterion = st.selectbox("정렬 기준", ["자전거 많은 순", "이름순", "거치율 낮은 순"])


# ── 공통 필터 적용 ─────────────────────────────────────────────
#df_all = load_data()
try:
    df_all = load_data()
except Exception as e:
    st.error("따릉이 데이터를 불러오지 못했습니다.")
    st.exception(e)
    st.stop()

filtered = search_stations(df_all, keyword)
if only_available:
    filtered = filter_available(filtered)
filtered = sort_stations(filtered, sort_criterion)


# ══════════════════════════════════════════════════════════════
# EDA 함수들
# ══════════════════════════════════════════════════════════════
def render_kpi_cards(df: pd.DataFrame) -> None:
    if df.empty:
        st.warning("데이터가 없습니다.")
        return

    total = len(df)
    total_bikes = int(df["parkingBikeTotCnt"].sum())
    avg_bikes = round(df["parkingBikeTotCnt"].mean(), 1)
    empty_count = int((df["parkingBikeTotCnt"] == 0).sum())
    full_count = int((df["parkingBikeTotCnt"] >= 10).sum())
    avg_shared = round(df["shared"].mean(), 1)

    cols = st.columns(6)
    cols[0].metric("전체 대여소", f"{total:,}개")
    cols[1].metric("전체 자전거", f"{total_bikes:,}대")
    cols[2].metric("평균 자전거", f"{avg_bikes}대")
    cols[3].metric("자전거 없음", f"{empty_count:,}개")
    cols[4].metric("자전거 충분", f"{full_count:,}개")
    cols[5].metric("평균 거치율", f"{avg_shared}%")


def _chart_status_pie(df: pd.DataFrame):
    counts = (
        df["status"]
        .value_counts()
        .reindex(_STATUS_ORDER, fill_value=0)
        .reset_index()
    )
    counts.columns = ["상태", "대여소 수"]
    fig = px.pie(
        counts,
        names="상태",
        values="대여소 수",
        color="상태",
        color_discrete_map=_STATUS_COLOR,
        title="대여소 상태 비율",
        hole=0.4,
    )
    fig.update_traces(textinfo="label+percent+value", textposition="outside")
    fig.update_layout(height=460, showlegend=True)
    return fig


def _chart_gu_avg(df: pd.DataFrame):
    tmp = df.copy()
    tmp["구"] = tmp["stationName"].apply(_extract_gu)
    gu_stats = (
        tmp.groupby("구")
        .agg(평균자전거=("parkingBikeTotCnt", "mean"), 대여소수=("stationName", "count"))
        .reset_index()
        .sort_values("평균자전거", ascending=False)
    )
    gu_stats["평균자전거"] = gu_stats["평균자전거"].round(1)
    fig = px.bar(
        gu_stats,
        x="구",
        y="평균자전거",
        color="평균자전거",
        color_continuous_scale="Blues",
        title="지역(구)별 평균 자전거 수",
        text="평균자전거",
        hover_data={"대여소수": True},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=460,
        xaxis_tickangle=-40,
        coloraxis_showscale=False,
        yaxis_title="평균 자전거 수 (대)",
    )
    return fig


def _chart_top10_rent(df: pd.DataFrame):
    top10 = df.nlargest(10, "parkingBikeTotCnt")[["stationName", "parkingBikeTotCnt"]].copy()
    top10["stationName"] = top10["stationName"].str.slice(0, 18)
    fig = px.bar(
        top10.sort_values("parkingBikeTotCnt"),
        x="parkingBikeTotCnt",
        y="stationName",
        orientation="h",
        title="지금 빌리기 좋은 대여소 TOP 10",
        labels={"parkingBikeTotCnt": "현재 자전거 수", "stationName": ""},
        color="parkingBikeTotCnt",
        color_continuous_scale="Greens",
        text="parkingBikeTotCnt",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(height=420, coloraxis_showscale=False)
    return fig


def _chart_top10_return(df: pd.DataFrame):
    top10 = df.nlargest(10, "availableRacks")[["stationName", "availableRacks"]].copy()
    top10["stationName"] = top10["stationName"].str.slice(0, 18)
    fig = px.bar(
        top10.sort_values("availableRacks"),
        x="availableRacks",
        y="stationName",
        orientation="h",
        title="지금 반납하기 좋은 대여소 TOP 10 (빈 거치대 많은 순)",
        labels={"availableRacks": "빈 거치대 수", "stationName": ""},
        color="availableRacks",
        color_continuous_scale="Oranges",
        text="availableRacks",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(height=420, coloraxis_showscale=False)
    return fig


def render_eda_section(df: pd.DataFrame) -> None:
    if df.empty:
        st.warning("표시할 데이터가 없습니다.")
        return

    render_kpi_cards(df)
    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 대여 가능 비율",
        "🏙️ 지역(구)별 현황",
        "🏆 TOP 10 대여소",
        "⚠️ 부족/없음 현황",
    ])

    with tab1:
        st.plotly_chart(_chart_status_pie(df), use_container_width=True)

    with tab2:
        st.plotly_chart(_chart_gu_avg(df), use_container_width=True)
        st.caption("대여소명에 구 이름이 포함된 경우만 분류됩니다. 포함되지 않으면 '기타'로 집계됩니다.")

    with tab3:
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(_chart_top10_rent(df), use_container_width=True)
        with col2:
            st.plotly_chart(_chart_top10_return(df), use_container_width=True)

    with tab4:
        col1, col2 = st.columns(2)

        with col1:
            shortage = (
                df[df["parkingBikeTotCnt"].between(1, 2)]
                [["stationName", "parkingBikeTotCnt", "status"]]
                .sort_values("parkingBikeTotCnt")
                .rename(columns={
                    "stationName": "대여소명",
                    "parkingBikeTotCnt": "현재 자전거",
                    "status": "상태",
                })
            )
            st.subheader(f"⚠️ 자전거 부족 ({len(shortage):,}개)")
            if shortage.empty:
                st.info("부족 대여소가 없습니다.")
            else:
                st.dataframe(shortage, use_container_width=True, hide_index=True)

        with col2:
            empty_df = df[df["parkingBikeTotCnt"] == 0]
            st.subheader(f"🔴 자전거 없음 ({len(empty_df):,}개)")
            with st.expander("목록 보기"):
                if empty_df.empty:
                    st.info("자전거 없는 대여소가 없습니다.")
                else:
                    st.dataframe(
                        empty_df[["stationName", "rackTotCnt"]].rename(
                            columns={"stationName": "대여소명", "rackTotCnt": "전체 거치대"}
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )


# ── 대여소 카드 ────────────────────────────────────────────────
def _station_card(row: pd.Series) -> str:
    color = _STATUS_COLOR.get(row["status"], "#6c757d")
    return f"""
    <div style="border:1px solid #e0e0e0; border-radius:12px; padding:16px;
                margin-bottom:12px; background:#fafafa;">
        <div style="font-weight:bold; margin-bottom:8px;">📍 {row['stationName']}</div>
        <div>자전거 <b>{int(row['parkingBikeTotCnt'])}대</b> / 거치대 {int(row['rackTotCnt'])}개</div>
        <div>거치율: {row['shared']}%</div>
        <div style="margin-top:6px;">
            <span style="background:{color}; color:white; padding:2px 8px;
                         border-radius:6px; font-size:0.85em;">{row['status']}</span>
        </div>
    </div>
    """


# ══════════════════════════════════════════════════════════════
# 페이지 1: EDA 현황 분석
# ══════════════════════════════════════════════════════════════
if page == "EDA 현황 분석":
    st.title("🚲 따릉이 Now")
    st.subheader("서울시 실시간 따릉이 대여소 현황")
    st.caption(f"마지막 업데이트: {get_last_updated()}")
    st.divider()

    eda_keyword = st.text_input(
        "🔍 지역/대여소명으로 EDA 범위 지정",
        placeholder="예: 홍대, 강남, 서울역, 잠실  (비워두면 전체 데이터 기준)",
    )
    eda_df = search_stations(df_all, eda_keyword)

    if eda_df.empty:
        st.warning("검색 결과가 없습니다. 다른 키워드를 입력해보세요.")
    else:
        if eda_keyword.strip():
            st.info(f"'{eda_keyword}' 검색 결과 **{len(eda_df):,}개** 대여소 기준으로 분석합니다.")
        render_eda_section(eda_df)


# ══════════════════════════════════════════════════════════════
# 페이지 2: 실시간 대여소 찾기
# ══════════════════════════════════════════════════════════════
elif page == "실시간 대여소 찾기":
    st.title("🚲 실시간 대여소 찾기")

    col_info1, col_info2, col_info3 = st.columns(3)
    col_info1.metric("전체 대여소", f"{len(df_all):,}개")
    col_info2.metric("검색 결과", f"{len(filtered):,}개")
    col_info3.metric("대여 가능", f"{len(df_all[df_all['parkingBikeTotCnt'] > 0]):,}개")
    st.divider()

    if filtered.empty:
        st.warning("검색 결과가 없습니다. 다른 키워드를 입력해보세요.")
    else:
        cols = st.columns(3)
        for i, (_, row) in enumerate(filtered.iterrows()):
            with cols[i % 3]:
                st.markdown(_station_card(row), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# 페이지 3: 지도에서 보기
# ══════════════════════════════════════════════════════════════
elif page == "지도에서 보기":
    st.title("🗺️ 지도에서 보기")

    map_data = filtered.dropna(subset=["stationLatitude", "stationLongitude"])
    if len(map_data) > 500:
        st.info(f"성능을 위해 상위 500개 대여소만 지도에 표시합니다. (전체 {len(map_data):,}개)")
        map_data = map_data.head(500)

    if map_data.empty:
        st.warning("표시할 대여소가 없습니다.")
    else:
        center_lat = map_data["stationLatitude"].mean()
        center_lon = map_data["stationLongitude"].mean()
        m = folium.Map(location=[center_lat, center_lon], zoom_start=13)

        for _, row in map_data.iterrows():
            folium.CircleMarker(
                location=[row["stationLatitude"], row["stationLongitude"]],
                radius=8,
                color=row["marker_color"],
                fill=True,
                fill_color=row["marker_color"],
                fill_opacity=0.85,
                popup=folium.Popup(
                    f"<b>{row['stationName']}</b><br>"
                    f"자전거: {int(row['parkingBikeTotCnt'])}대<br>"
                    f"거치대: {int(row['rackTotCnt'])}개<br>"
                    f"거치율: {row['shared']}%<br>"
                    f"상태: {row['status']}",
                    max_width=220,
                ),
            ).add_to(m)

        st_folium(m, use_container_width=True, height=600)
        st.caption("🟢 충분(10대+) &nbsp;&nbsp; 🔵 보통(3~9대) &nbsp;&nbsp; 🟠 부족(1~2대) &nbsp;&nbsp; 🔴 없음(0대)")


# ══════════════════════════════════════════════════════════════
# 페이지 4: 빠른 추천
# ══════════════════════════════════════════════════════════════
elif page == "빠른 추천":
    st.title("⚡ 빠른 추천")

    _DISPLAY_COLS = {
        "stationName":       "대여소명",
        "parkingBikeTotCnt": "현재 자전거",
        "rackTotCnt":        "전체 거치대",
        "shared":            "거치율(%)",
        "availableRacks":    "빈 거치대",
        "status":            "상태",
    }

    st.subheader("🏆 지금 빌리기 좋은 대여소 TOP 10")
    top10 = (
        df_all[df_all["parkingBikeTotCnt"] > 0]
        .nlargest(10, "parkingBikeTotCnt")
        [list(_DISPLAY_COLS.keys())]
        .rename(columns=_DISPLAY_COLS)
    )
    st.dataframe(top10, use_container_width=True, hide_index=True)

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("⚠️ 자전거 부족 대여소")
        shortage = (
            df_all[df_all["parkingBikeTotCnt"].between(1, 2)]
            [["stationName", "parkingBikeTotCnt", "status"]]
            .rename(columns={"stationName": "대여소명", "parkingBikeTotCnt": "현재 자전거", "status": "상태"})
            .head(10)
        )
        st.dataframe(shortage, use_container_width=True, hide_index=True)

    with col2:
        st.subheader("🔴 자전거 없는 대여소")
        empty = (
            df_all[df_all["parkingBikeTotCnt"] == 0]
            [["stationName", "rackTotCnt", "status"]]
            .rename(columns={"stationName": "대여소명", "rackTotCnt": "전체 거치대", "status": "상태"})
            .head(10)
        )
        st.dataframe(empty, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("📦 반납 여유 있는 대여소 (빈 거치대 많은 곳)")
    st.caption("거치율이 낮을수록 반납 공간이 많습니다. 실제 반납 가능 여부는 현장 확인 권장.")
    returnable = (
        df_all[df_all["availableRacks"] > 5]
        .nlargest(10, "availableRacks")
        [list(_DISPLAY_COLS.keys())]
        .rename(columns=_DISPLAY_COLS)
    )
    st.dataframe(returnable, use_container_width=True, hide_index=True)
