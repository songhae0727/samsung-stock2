import numpy as np
import os
import json
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'model', 'samsung_lstm.keras')
META_PATH = MODEL_PATH.replace('.keras', '_meta.json')
SEQ_LEN = 60
OUTPUT_STEPS = 7
FEATURES = ['Close', 'Volume', 'MA5', 'MA20', 'RSI']

def build_model(input_shape: tuple, output_steps: int) -> tf.keras.Model:
    model = Sequential([
        LSTM(50, return_sequences=True, input_shape=input_shape),
        Dropout(0.2),
        LSTM(50, return_sequences=False),
        Dropout(0.2),
        Dense(output_steps)
    ])
    model.compile(optimizer='adam', loss='mean_squared_error')
    return model

def prepare_sequences(data: np.ndarray, seq_len: int, output_steps: int):
    X, y = [], []
    for i in range(seq_len, len(data) - output_steps + 1):
        X.append(data[i - seq_len:i])
        y.append(data[i:i + output_steps, 0])  # Close is index 0
    return np.array(X), np.array(y)

def _build_scaler_from_meta(meta: dict) -> MinMaxScaler:
    scaler = MinMaxScaler()
    data_min = np.array(meta['scaler_min'])
    data_max = np.array(meta['scaler_max'])
    scaler.data_min_ = data_min
    scaler.data_max_ = data_max
    scaler.data_range_ = data_max - data_min
    scaler.scale_ = np.where(scaler.data_range_ == 0, 0, 1.0 / scaler.data_range_)
    scaler.min_ = -data_min * scaler.scale_
    scaler.n_features_in_ = len(FEATURES)
    scaler.n_samples_seen_ = 0
    scaler.feature_names_in_ = None
    return scaler

def train_and_save(df) -> None:
    """모델 학습 후 가중치와 스케일러 메타 저장."""
    data = df[FEATURES].values
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(data)

    split = int(len(scaled) * 0.8)
    X_train, y_train = prepare_sequences(scaled[:split], SEQ_LEN, OUTPUT_STEPS)
    X_val, y_val = prepare_sequences(scaled[split - SEQ_LEN:], SEQ_LEN, OUTPUT_STEPS)

    model = build_model(input_shape=(SEQ_LEN, len(FEATURES)), output_steps=OUTPUT_STEPS)
    early_stop = EarlyStopping(patience=10, restore_best_weights=True)
    model.fit(X_train, y_train, validation_data=(X_val, y_val),
              epochs=100, batch_size=32, callbacks=[early_stop], verbose=0)

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    model.save(MODEL_PATH)
    with open(META_PATH, 'w') as f:
        json.dump({
            'close_min': float(scaler.data_min_[0]),
            'close_max': float(scaler.data_max_[0]),
            'scaler_min': scaler.data_min_.tolist(),
            'scaler_max': scaler.data_max_.tolist(),
        }, f)

def predict_next_days(df, days: int = 7) -> list[dict]:
    """학습된 모델로 다음 days일 예측. 모델 없으면 즉시 학습."""
    if not os.path.exists(MODEL_PATH):
        train_and_save(df)

    model = load_model(MODEL_PATH)
    with open(META_PATH) as f:
        meta = json.load(f)

    scaler = _build_scaler_from_meta(meta)
    scaled = scaler.transform(df[FEATURES].values)
    last_seq = scaled[-SEQ_LEN:].reshape(1, SEQ_LEN, len(FEATURES))
    raw_pred = model.predict(last_seq, verbose=0)[0]

    close_min = meta['close_min']
    close_max = meta['close_max']
    prices = raw_pred * (close_max - close_min) + close_min

    base_price = float(df['Close'].iloc[-1])
    last_date = df.index[-1]
    confidence_levels = [92, 88, 83, 79, 75, 70, 65]
    day_map = {'Mon': '월', 'Tue': '화', 'Wed': '수', 'Thu': '목', 'Fri': '금'}

    results = []
    for i in range(min(days, len(prices))):
        next_date = last_date + timedelta(days=i + 1)
        while next_date.weekday() >= 5:
            next_date += timedelta(days=1)

        predicted_price = round(float(prices[i]) / 100) * 100
        change = predicted_price - base_price
        change_pct = (change / base_price) * 100

        label = next_date.strftime('%m/%d (%a)')
        for en, ko in day_map.items():
            label = label.replace(en, ko)

        results.append({
            'date': next_date.strftime('%Y-%m-%d'),
            'day_label': label,
            'price': predicted_price,
            'change': round(change),
            'change_pct': round(change_pct, 2),
            'confidence': confidence_levels[i],
        })

    return results

def calculate_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """MAPE 기반 정확도 계산."""
    mape = float(np.mean(np.abs((y_true - y_pred) / np.where(y_true == 0, 1, y_true))) * 100)
    return {'mape': round(mape, 2), 'accuracy': round(max(0.0, 100 - mape), 1)}

def get_model_accuracy(df) -> dict:
    """검증 세트로 1일/3일/7일 정확도 계산."""
    if not os.path.exists(MODEL_PATH):
        train_and_save(df)

    model = load_model(MODEL_PATH)
    with open(META_PATH) as f:
        meta = json.load(f)

    scaler = _build_scaler_from_meta(meta)
    close_min, close_max = meta['close_min'], meta['close_max']

    scaled = scaler.transform(df[FEATURES].values)
    split = int(len(scaled) * 0.8)
    X_val, y_val_s = prepare_sequences(scaled[split - SEQ_LEN:], SEQ_LEN, OUTPUT_STEPS)

    y_pred_s = model.predict(X_val, verbose=0)
    y_true = y_val_s * (close_max - close_min) + close_min
    y_pred = y_pred_s * (close_max - close_min) + close_min

    return {
        '1d': calculate_accuracy(y_true[:, 0], y_pred[:, 0])['accuracy'],
        '3d': calculate_accuracy(y_true[:, 2], y_pred[:, 2])['accuracy'],
        '7d': calculate_accuracy(y_true[:, 6], y_pred[:, 6])['accuracy'],
    }
