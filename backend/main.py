import os
import math
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scheduler import refresh_data, get_cache, start_scheduler

ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")

@asynccontextmanager
async def lifespan(app: FastAPI):
    refresh_data()
    scheduler = start_scheduler()
    yield
    scheduler.shutdown()

app = FastAPI(title="삼성전자 주가 예측 API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN] if ALLOWED_ORIGIN != "*" else ["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/current-price")
def current_price():
    cache = get_cache()
    if cache['current_price']:
        return cache['current_price']
    from data_collector import get_current_price
    return get_current_price()

@app.get("/prediction")
def prediction():
    cache = get_cache()
    if cache['predictions']:
        return {"predictions": cache['predictions']}
    from data_collector import fetch_stock_data, compute_features
    from model import predict_next_days
    df = fetch_stock_data(period='2y')
    df = compute_features(df)
    return {"predictions": predict_next_days(df, days=7)}

@app.get("/history")
def history(days: int = 30):
    cache = get_cache()
    df = cache['df']
    if df is None:
        from data_collector import fetch_stock_data, compute_features
        df = fetch_stock_data(period='2y')
        df = compute_features(df)

    subset = df.tail(days)
    return {
        "dates": [d.strftime('%Y-%m-%d') for d in subset.index],
        "prices": [round(float(p)) for p in subset['Close']],
        "ma5": [round(float(v)) if not math.isnan(float(v)) else None for v in subset['MA5']],
        "ma20": [round(float(v)) if not math.isnan(float(v)) else None for v in subset['MA20']],
    }

@app.get("/accuracy")
def accuracy():
    cache = get_cache()
    if cache['accuracy']:
        return cache['accuracy']
    from data_collector import fetch_stock_data, compute_features
    from model import get_model_accuracy
    df = fetch_stock_data(period='2y')
    df = compute_features(df)
    return get_model_accuracy(df)
