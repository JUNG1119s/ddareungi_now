import pandas as pd

_NUMERIC_COLS = [
    "rackTotCnt",
    "parkingBikeTotCnt",
    "shared",
    "stationLatitude",
    "stationLongitude",
]

# (최소 대수, 상태 레이블, 지도 마커 색상)
_STATUS_LEVELS = [
    (10, "🟢 충분", "green"),
    (3,  "🟡 보통", "blue"),
    (1,  "🟠 부족", "orange"),
    (0,  "🔴 없음", "red"),
]


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in _NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["status"] = df["parkingBikeTotCnt"].apply(_get_status)
    df["marker_color"] = df["parkingBikeTotCnt"].apply(_get_color)
    df["availableRacks"] = (df["rackTotCnt"] - df["parkingBikeTotCnt"]).clip(lower=0)

    df = df.dropna(subset=["stationLatitude", "stationLongitude"])
    df = df[(df["stationLatitude"] != 0) & (df["stationLongitude"] != 0)]

    return df.reset_index(drop=True)


def _get_status(count: float) -> str:
    for threshold, label, _ in _STATUS_LEVELS:
        if count >= threshold:
            return label
    return "🔴 없음"


def _get_color(count: float) -> str:
    for threshold, _, color in _STATUS_LEVELS:
        if count >= threshold:
            return color
    return "red"


def search_stations(df: pd.DataFrame, keyword: str) -> pd.DataFrame:
    if not keyword.strip():
        return df
    return df[df["stationName"].str.contains(keyword.strip(), case=False, na=False)]


def filter_available(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["parkingBikeTotCnt"] > 0]


def sort_stations(df: pd.DataFrame, criterion: str) -> pd.DataFrame:
    sorts = {
        "자전거 많은 순": ("parkingBikeTotCnt", False),
        "이름순":         ("stationName",        True),
        "거치율 낮은 순": ("shared",             True),
    }
    col, asc = sorts.get(criterion, ("parkingBikeTotCnt", False))
    return df.sort_values(col, ascending=asc)
