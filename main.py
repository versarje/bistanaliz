import os
import requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def calculate_rsi(series, period=14):
    """Sıfırdan RSI Hesaplama Fonksiyonu"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_bist_data_zero(symbol):
    """Yahoo Finance API üzerinden sıfırdan BİST verisi çeker"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.IS?range=3mo&interval=1d"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    res = requests.get(url, headers=headers, timeout=10)
    data = res.json()
    
    result = data['chart']['result'][0]
    timestamps = result['timestamp']
    quote = result['indicators']['quote'][0]
    
    df = pd.DataFrame({
        'Date': pd.to_datetime(timestamps, unit='s'),
        'Close': quote['close'],
        'Volume': quote['volume']
    }).dropna()
    
    return df

def get_bist_news_zero():
    """Haber başlıklarını çeker"""
    try:
        url = "https://www.bloomberght.com/borsa"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.content, 'html.parser')
        headlines = [h.text.strip() for h in soup.find_all('span', limit=5) if len(h.text.strip()) > 15]
        return headlines[:3]
    except Exception as e:
        return [f"Haber çekilemedi: {e}"]

def analiz_ve_tahmin_yap():
    hisseler = ["THYAO", "GARAN", "EREGL", "ASELS", "TUPRS", "KCHOL"]
    
    rapor = "📊 **SIFIRDAN BİST PİYASA & TAHMİN RAPORU** 📊\n\n"
    rapor += "📈 **HİSSE TAHMİNLERİ VE HACİM BİLGİSİ**\n"
    
    for symbol in hisseler:
        try:
            df = get_bist_data_zero(symbol)
            
            if df.empty or len(df) < 50:
                continue
                
            son_fiyat = df["Close"].iloc[-1]
            onceki_fiyat = df["Close"].iloc[-2]
            hacim_son = df["Volume"].iloc[-1]
            hacim_ort = df["Volume"].tail(10).mean()
            
            degisim = ((son_fiyat - onceki_fiyat) / onceki_fiyat) * 100
            
            # SIFIRDAN İNDİKATÖR HESAPLAMALARI
            df["RSI"] = calculate_rsi(df["Close"], period=14)
            df["SMA20"] = df["Close"].rolling(window=20).mean()
            df["SMA50"] = df["Close"].rolling(window=50).mean()
            
            rsi = df["RSI"].iloc[-1]
            sma20 = df["SMA20"].iloc[-1]
            sma50 = df["SMA50"].iloc[-1]
            
            hacim_durum = "🔥 Yüksek Hacim" if hacim_son > (hacim_ort * 1.3) else "💤 Normal Hacim"
            
            # Yön ve Tahmin Algoritması
            if rsi < 32 and son_fiyat > sma20:
                tahmin = "🚀 GÜÇLÜ YÜKSELİŞ TAHMİNİ (Aşırı Satım Tepkisi)"
            elif rsi > 70:
                tahmin = "⚠️ DÜŞÜŞ / DÜZELTME RİSKİ (Aşırı Alım Bölgesi)"
            elif son_fiyat > sma20 and sma20 > sma50:
                tahmin = "📈 YÜKSELİŞ TRENDİ DEVAM EDİYOR"
            elif son_fiyat < sma20:
                tahmin = "📉 DÜŞÜŞ BASKISI VAR"
            else:
                tahmin = "🟡 NÖTR / YATAY SEYİR"
                
            rapor += f"🔹 **{symbol}**: {son_fiyat:.2f} TL (%{degisim:+.2f})\n"
            rapor += f"   • RSI(14): {rsi:.1f}\n"
            rapor += f"   • Hacim: {hacim_durum}\n"
            rapor += f"   • Tahmin: {tahmin}\n\n"
            
        except Exception as e:
            rapor += f"❌ {symbol} çekilemedi: {e}\n\n"
            
    rapor += "📰 **SON PİYASA BAŞLIKLARI**\n"
    haberler = get_bist_news_zero()
    for h in haberler:
        rapor += f"• {h}\n"
        
    print(rapor)
    
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": rapor, "parse_mode": "Markdown"})

if __name__ == "__main__":
    analiz_ve_tahmin_yap()
