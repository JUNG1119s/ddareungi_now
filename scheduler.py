"""
독립 실행 스크립트: 1시간마다 따릉이 데이터를 수집해 CSV로 저장합니다.
실행: python scheduler.py
"""

import time
import logging
from pathlib import Path
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from api import fetch_all_stations
from utils import preprocess

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
CSV_PATH = DATA_DIR / "bike_latest.csv"
TIMESTAMP_PATH = DATA_DIR / "last_updated.txt"
INTERVAL_HOURS = 1


def collect_and_save() -> None:
    logger.info("데이터 수집 시작...")
    try:
        df = fetch_all_stations()
        df = preprocess(df)

        DATA_DIR.mkdir(exist_ok=True)
        df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
        TIMESTAMP_PATH.write_text(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            encoding="utf-8",
        )
        logger.info(f"저장 완료 — {len(df)}개 대여소")
    except Exception as exc:
        logger.error(f"수집 실패: {exc}")


def main() -> None:
    collect_and_save()  # 시작 즉시 1회 실행

    scheduler = BackgroundScheduler()
    scheduler.add_job(collect_and_save, "interval", hours=INTERVAL_HOURS)
    scheduler.start()
    logger.info(f"스케줄러 시작 ({INTERVAL_HOURS}시간 간격)")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("스케줄러 종료")


if __name__ == "__main__":
    main()
