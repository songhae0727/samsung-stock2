import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import pytz

TICKER = "005930.KS"

def fetch_stock_data(period: str = "2y") -> pd.DataFrame | None:
    """yfinance로 삼성전자 주가 데이터 수집. 실패 시 None 반환."""
    try:
        ticker = yf.Ticker(TICKER)
        df = ticker.history(period=period)
        if df.empty:
            return None
        if df.index.tz is not None:
            df.index = df.index.tz_convert(None)
        else:
            df.index = df.index.tz_localize(None)
        return df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    except Exception:
        return None

def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """종가 기반 MA5, MA20, RSI(14) 계산."""
    df = df.copy()
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()

    delta = df['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    df['RSI'] = df['RSI'].fillna(50)

    return df.dropna()

def _safe_float(val) -> float | None:
    import math
    try:
        v = float(val)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None

def get_current_price() -> dict:
    """현재 주가, 전일 대비 등락 반환. 장 마감 시 최근 종가 사용."""
    ticker = yf.Ticker(TICKER)
    info = ticker.fast_info

    price = _safe_float(info.last_price)
    prev_close = _safe_float(info.previous_close)

    if price is None or prev_close is None:
        df = ticker.history(period='5d')
        if df.empty:
            return {"price": 0, "change": 0, "change_pct": 0.0, "updated_at": "N/A"}
        closes = df['Close'].dropna()
        price = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else price

    change = price - prev_close
    change_pct = (change / prev_close) * 100 if prev_close != 0 else 0.0

    kst = pytz.timezone('Asia/Seoul')
    now_kst = datetime.now(kst).strftime('%Y-%m-%d %H:%M KST')

    return {
        "price": round(price),
        "change": round(change),
        "change_pct": round(change_pct, 2),
        "updated_at": now_kst
    }
