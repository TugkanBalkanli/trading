import os
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# --- AYARLAR ---
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Tarama aralığı (saniye) - her 15 dakikada bir tara
SCAN_INTERVAL = 900

# --- TELEGRAM MESAJ GÖNDER ---
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram hatası: {e}")

# --- BİNANCE'TEN VERİ ÇEK ---
def get_klines(symbol, interval="15m", limit=100):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        df = pd.DataFrame(data, columns=[
            "time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        return df
    except Exception as e:
        print(f"{symbol} kline hatası: {e}")
        return None

# --- FUTURES SEMBOL LİSTESİ ---
def get_futures_symbols():
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        symbols = [
            s["symbol"] for s in data["symbols"]
            if s["status"] == "TRADING" and s["symbol"].endswith("USDT")
        ]
        return symbols
    except Exception as e:
        print(f"Sembol listesi hatası: {e}")
        return []

# --- OI VERİSİ ---
def get_oi(symbol):
    url = "https://fapi.binance.com/fapi/v1/openInterest"
    try:
        r = requests.get(url, params={"symbol": symbol}, timeout=10)
        data = r.json()
        return float(data.get("openInterest", 0))
    except:
        return 0

# --- 24S HACİM ---
def get_24h_volume(symbol):
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    try:
        r = requests.get(url, params={"symbol": symbol}, timeout=10)
        data = r.json()
        return float(data.get("quoteVolume", 0))
    except:
        return 0

# --- EMA HESAPLA ---
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

# --- RSI HESAPLA ---
def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# --- BTC DURUMU KONTROL ---
def check_btc():
    df = get_klines("BTCUSDT", interval="4h", limit=50)
    if df is None:
        return False
    close = df["close"]
    ema21 = ema(close, 21)
    last_close = close.iloc[-1]
    last_ema21 = ema21.iloc[-1]
    # BTC EMA21 üstünde veya çok yakınsa (yüzde 2 tolerans)
    return last_close >= last_ema21 * 0.98

# --- SETUP KONTROL ---
def check_setup(symbol):
    df = get_klines(symbol, interval="15m", limit=100)
    if df is None or len(df) < 50:
        return False, {}

    close = df["close"]
    volume = df["volume"]

    ema21_series = ema(close, 21)
    rsi_series = rsi(close, 14)
    rsi_sma = rsi_series.rolling(14).mean()

    last_close = close.iloc[-1]
    last_ema21 = ema21_series.iloc[-1]
    last_rsi = rsi_series.iloc[-1]
    last_rsi_sma = rsi_sma.iloc[-1]

    # Son 3 mumda hacim artıyor mu
    vol_increasing = (
        volume.iloc[-1] > volume.iloc[-2] > volume.iloc[-3]
    )

    # Şartlar
    above_ema21 = last_close > last_ema21
    rsi_ok = 45 <= last_rsi <= 65
    rsi_above_sma = last_rsi > last_rsi_sma

    if above_ema21 and rsi_ok and rsi_above_sma and vol_increasing:
        return True, {
            "close": last_close,
            "ema21": round(last_ema21, 6),
            "rsi": round(last_rsi, 1),
            "rsi_sma": round(last_rsi_sma, 1)
        }

    return False, {}

# --- OI/HACİM ORANI KONTROL ---
def check_oi_ratio(symbol):
    oi = get_oi(symbol)
    vol = get_24h_volume(symbol)
    if vol == 0:
        return False, 0
    ratio = (oi / vol) * 100
    # Fiyatı da çek, OI'yi USDT'ye çevir
    # OI coin cinsindendir, yaklaşık hesap için geçiyoruz
    return ratio >= 10, round(ratio, 1)

# --- ANA TARAMA ---
def scan():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Tarama başladı...")

    # BTC kontrolü
    btc_ok = check_btc()
    if not btc_ok:
        print("BTC EMA21 altında, tarama atlandı.")
        return

    print("BTC durumu OK, coinler taranıyor...")

    symbols = get_futures_symbols()
    print(f"Toplam {len(symbols)} coin taranacak.")

    alerts = []

    for symbol in symbols:
        try:
            setup_ok, data = check_setup(symbol)
            if not setup_ok:
                continue

            oi_ok, oi_ratio = check_oi_ratio(symbol)
            if not oi_ok:
                continue

            alerts.append({
                "symbol": symbol,
                "data": data,
                "oi_ratio": oi_ratio
            })

            time.sleep(0.2)  # Rate limit için bekle

        except Exception as e:
            print(f"{symbol} hata: {e}")
            continue

    if alerts:
        for alert in alerts:
            s = alert["symbol"]
            d = alert["data"]
            msg = (
                f"🚨 <b>SETUP OLUŞTU: {s}</b>\n\n"
                f"💰 Fiyat: {d['close']}\n"
                f"📊 EMA21: {d['ema21']}\n"
                f"📈 RSI: {d['rsi']} (SMA: {d['rsi_sma']})\n"
                f"📦 OI/Hacim Oranı: %{alert['oi_ratio']}\n\n"
                f"⏰ {datetime.now().strftime('%H:%M:%S')}\n"
                f"🕯 M15 grafiği kontrol et!"
            )
            send_telegram(msg)
            print(f"Alert gönderildi: {s}")
    else:
        print("Setup bulunamadı.")

# --- BAŞLAT ---
if __name__ == "__main__":
    send_telegram("🤖 Trading Bot başlatıldı! M15 setup taraması aktif.")
    while True:
        scan()
        print(f"Sonraki tarama {SCAN_INTERVAL // 60} dakika sonra...")
        time.sleep(SCAN_INTERVAL)
