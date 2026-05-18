# Trading Bot - Kurulum Rehberi

## Ne Yapar?
- Her 15 dakikada bir tüm Binance Futures coinlerini tarar
- BTC EMA21 üstündeyse tarama yapar, altındaysa atlar
- M15 setup şartları: Fiyat EMA21 üstü + RSI 45-65 + RSI SMA üstü + Hacim artıyor
- OI/Hacim oranı %10 üstündeyse alert gönderir
- Telegram'a bildirim atar

## Railway'e Kurulum

### 1. GitHub'a Yükle
- github.com'a git, ücretsiz hesap aç
- "New Repository" oluştur, "trading-bot" adını ver
- bot.py ve requirements.txt dosyalarını yükle

### 2. Railway Kurulumu
- railway.app'e git, GitHub hesabınla giriş yap
- "New Project" → "Deploy from GitHub repo" seç
- Az önce oluşturduğun repoyu seç

### 3. Environment Variables Ekle
Railway'de projeye gir → Variables sekmesi → şunları ekle:

```
BINANCE_API_KEY = senin_api_keyin
TELEGRAM_BOT_TOKEN = senin_bot_tokenin
TELEGRAM_CHAT_ID = senin_chat_idin
```

### 4. Deploy Et
Variables ekledikten sonra Railway otomatik deploy eder.
Logs sekmesinden çalışıp çalışmadığını görebilirsin.

## Notlar
- Railway ücretsiz planda aylık 500 saat veriyor
- Bot 7/24 çalışır, sen uyurken bile alarm gönderir
- Binance API key sadece Read Only, güvenli
