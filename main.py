import os
import requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def calculate_rsi(series, period=14):
    """Sıfırdan RSI Hesaplama"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series, fast=12, slow=26, signal=9):
    """Sıfırdan MACD Hesaplama"""
    exp1 = series.ewm(span=fast, adjust=False).mean()
    exp2 = series.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def calculate_bollinger(series, window=20, std_dev=2):
    """Sıfırdan Bollinger Bantları Hesaplama"""
    sma = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    return upper_band, lower_band

def get_bist_data_zero(symbol):
    """Yahoo Finance API üzerinden BİST verisi çeker"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.IS?range=6mo&interval=1d"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    res = requests.get(url, headers=headers, timeout=10)
    data = res.json()
    
    result = data['chart']['result'][0]
    timestamps = result.get('timestamp', [])
    
    if not timestamps:
        return pd.DataFrame()
        
    quote = result['indicators']['quote'][0]
    
    df = pd.DataFrame({
        'Date': pd.to_datetime(timestamps, unit='s'),
        'Close': quote['close'],
        'Volume': quote['volume']
    }).dropna()
    
    return df

def get_bist100_trend():
    """BİST 100 Endeksinin (XU100) Genel Yönünü Getirir"""
    try:
        df = get_bist_data_zero("XU100")
        if df.empty:
            return "NÖTR"
        son_fiyat = df["Close"].iloc[-1]
        sma20 = df["Close"].rolling(window=20).mean().iloc[-1]
        return "POZİTİF" if son_fiyat > sma20 else "NEGATİF"
    except:
        return "NÖTR"

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

def hisse_analiz_et(symbol, xu100_durum):
    try:
        df = get_bist_data_zero(symbol)
        
        if df.empty or len(df) < 5:
            return f"🔹 **{symbol}**: Veri bulunamadı veya henüz yetersiz.\n\n"
            
        son_fiyat = df["Close"].iloc[-1]
        onceki_fiyat = df["Close"].iloc[-2]
        hacim_son = df["Volume"].iloc[-1]
        
        hacim_periyot = min(len(df), 10)
        hacim_ort = df["Volume"].tail(hacim_periyot).mean()
        
        degisim = ((son_fiyat - onceki_fiyat) / onceki_fiyat) * 100
        
        # 1. Gelişmiş İndikatör Hesaplamaları
        rsi_val = calculate_rsi(df["Close"], period=14).iloc[-1] if len(df) >= 15 else None
        sma20_val = df["Close"].rolling(window=min(len(df), 20)).mean().iloc[-1]
        sma50_val = df["Close"].rolling(window=50).mean().iloc[-1] if len(df) >= 50 else None
        
        upper_band, lower_band = calculate_bollinger(df["Close"])
        bollinger_alt = lower_band.iloc[-1] if len(df) >= 20 else None
        
        macd_line, signal_line = calculate_macd(df["Close"])
        macd_val = macd_line.iloc[-1] if len(df) >= 26 else None
        macd_sig = signal_line.iloc[-1] if len(df) >= 26 else None
        
        hacim_durum = "🔥 Yüksek Hacim" if hacim_son > (hacim_ort * 1.3) else "💤 Normal Hacim"
        
        # 2. Puanlama (Skorlama) Sistemi
        skor = 0
        
        if rsi_val is not None and rsi_val < 35:
            skor += 1.5  # Aşırı satım bölgesi (Alım fırsatı)
        elif rsi_val is not None and rsi_val > 65:
            skor -= 1.5  # Aşırı alım bölgesi (Düzeltme riski)
            
        if son_fiyat > sma20_val:
            skor += 1.0  # Kısa vadeli yükseliş trendi
            
        if sma50_val and sma20_val > sma50_val:
            skor += 1.0  # Orta vadeli yükseliş trendi
            
        if macd_val is not None and macd_sig is not None and macd_val > macd_sig:
            skor += 1.0  # MACD Al sinyali
            
        if bollinger_alt is not None and son_fiyat <= bollinger_alt:
            skor += 1.0  # Alt banta temas (Tepki yükselişi beklentisi)
            
        if hacim_son > (hacim_ort * 1.3) and degisim > 0:
            skor += 0.5  # Hacimli para girişi
            
        if xu100_durum == "POZİTİF":
            skor += 0.5  # Genel borsa desteği
            
        # 3. Skor İle Tahmin Kararı
        if skor >= 4.0:
            tahmin = f"🚀 GÜÇLÜ ALIM SİNYALİ (Skor: {skor:.1f}/5)"
        elif skor >= 2.5:
            tahmin = f"📈 POZİTİF SEYİR (Skor: {skor:.1f}/5)"
        elif skor >= 1.0:
            tahmin = f"🟡 NÖTR / TEMKİNLİ (Skor: {skor:.1f}/5)"
        else:
            tahmin = f"📉 DÜŞÜŞ BASKISI VAR (Skor: {skor:.1f}/5)"
            
        rsi_str = f"{rsi_val:.1f}" if rsi_val is not None else "N/A"
        
        out = f"🔹 **{symbol}**: {son_fiyat:.2f} TL (%{degisim:+.2f})\n"
        out += f"   • RSI: {rsi_str} | Hacim: {hacim_durum}\n"
        out += f"   • Tahmin: {tahmin}\n\n"
        return out
        
    except Exception as e:
        return f"❌ {symbol} çekilemedi: {e}\n\n"

def analiz_ve_tahmin_yap():
    ana_hisseler = ["THYAO", "GARAN", "EREGL", "ASELS", "TUPRS", "KCHOL"]
    halka_arzlar = ["KARCL", "MASFN", "METEN", "SSAAT", "SARAE", "ALBTN"]
    
    xu100_durum = get_bist100_trend()
    
    rapor = "📊 **BİST ÇOKLU ANALİZ VE TAHMİN RAPORU** 📊\n"
    rapor += f"🏛 **BİST 100 Genel Trendi:** {xu100_durum}\n\n"
    
    rapor += "📈 **KÖKLÜ BİST HİSSELERİ**\n"
    for symbol in ana_hisseler:
        rapor += hisse_analiz_et(symbol, xu100_durum)
        
    rapor += "🆕 **YENİ HALKA ARZ TAHTALARI (50+ GÜN)**\n"
    for symbol in halka_arzlar:
        rapor += hisse_analiz_et(symbol, xu100_durum)
            
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
