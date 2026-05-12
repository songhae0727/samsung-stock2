from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)

_cached_data = {
    "df": None,
    "current_price": None,
    "predictions": None,
    "accuracy": None
}

def refresh_data():
    from data_collector import fetch_stock_data, compute_features, get_current_price
    from model import predict_next_days, get_model_accuracy

    logger.info("데이터 갱신 시작...")
    try:
        df = fetch_stock_data(period='2y')
        if df is None:
            logger.warning("yfinance 수집 실패 — 캐시 유지")
            return
        df = compute_features(df)
        _cached_data['df'] = df
        _cached_data['current_price'] = get_current_price()
        _cached_data['predictions'] = predict_next_days(df, days=7)
        _cached_data['accuracy'] = get_model_accuracy(df)
        logger.info("데이터 갱신 완료")
    except Exception as e:
        logger.error(f"갱신 오류: {e}")

def get_cache() -> dict:
    return _cached_data

def start_scheduler():
    scheduler = BackgroundScheduler(timezone='Asia/Seoul')
    scheduler.add_job(refresh_data, CronTrigger(hour=15, minute=35))
    scheduler.start()
    return scheduler
