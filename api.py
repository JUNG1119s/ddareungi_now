import os
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

_API_KEY = st.secrets.get("SEOUL_API_KEY", os.getenv("SEOUL_API_KEY"))

_BASE_URL = "http://openapi.seoul.go.kr:8088"
_BATCH_SIZE = 1000


def _fetch_range(start: int, end: int) -> tuple[list[dict], int]:
    if not _API_KEY:
        raise RuntimeError(
            "SEOUL_API_KEY가 없습니다. Streamlit Cloud의 Settings → Secrets에 API 키를 등록하세요."
        )

    url = f"{_BASE_URL}/{_API_KEY}/json/bikeList/{start}/{end}/"

    resp = requests.get(url, timeout=10)

    if resp.status_code != 200:
        raise RuntimeError(
            f"API 요청 실패: status={resp.status_code}, 응답={resp.text[:500]}"
        )

    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(
            f"API 응답이 JSON이 아닙니다. 응답 앞부분: {resp.text[:500]}"
        )

    body = data.get("rentBikeStatus", {})

    result_code = body.get("RESULT", {}).get("CODE", "")
    if result_code != "INFO-000":
        raise ValueError(
            f"API 오류: {body.get('RESULT', {}).get('MESSAGE', '알 수 없는 오류')}"
        )

    total = int(body.get("list_total_count", 0))
    rows = body.get("row", [])

    return rows, total


def fetch_all_stations() -> pd.DataFrame:
    all_rows: list[dict] = []
    start = 1

    batch, total = _fetch_range(start, start + _BATCH_SIZE - 1)
    all_rows.extend(batch)

    while len(all_rows) < total:
        start += _BATCH_SIZE
        end = min(start + _BATCH_SIZE - 1, total)

        batch, _ = _fetch_range(start, end)
        all_rows.extend(batch)

        if not batch:
            break

    return pd.DataFrame(all_rows)