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
    # 1. Köklü BİST Hisseleri
    ana_hisseler = ["THYAO", "GARAN", "EREGL", "ASELS", "TUPRS", "KCHOL"]
    
    # 2. BİST Yeni Halka Arz / Yakın Zaman Halka Arz Hisseleri
    # (Örnek: BINBN, KOCMT, MHRGY, BEGYO, ENERY, TABGD - Takip etmek istediğiniz yeni tahtaları buraya ekleyebilirsiniz)
    halka_arzlar = ["BINBN", "BEGYO", "ENERY", "TABGD", "SURGY"]
    
    rapor = "📊 **SIFIRDAN BİST PİYASA & TAHMİN RAPORU** 📊\n\n"
    
    # --- ANA HİSSELER ANALİZİ ---
    rapor += "📈 **KÖKLÜ BİST HİSSELERİ**\n"
    for symbol in ana_hisseler:
        rapor += hisse_analiz_et(symbol)
        
    # --- YENİ HALKA ARZ TAHTALARI ANALİZİ ---
    rapor += "🆕 **YENİ HALKA ARZ TAHTALARI**\n"
    for symbol in halka_arzlar:
        rapor += hisse_analiz_et(symbol, is_halka_arz=True)
            
    # --- PİYASA HABERLERİ ---
    rapor += "📰 **SON PİYASA BAŞLIKLARI**\n"
    haberler = get_bist_news_zero()
    for h in haberler:
        rapor += f"• {h}\n"
        
    print(rapor)
    
    # Telegram Gönderimi
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": rapor, "parse_mode": "Markdown"})

def hisse_analiz_et(symbol, is_halka_arz=False):
    try:
        df = get_bist_data_zero(symbol)
        
        if df.empty or len(df) < 5:
            return f"🔹 **{symbol}**: Veri henüz yetersiz (Çok yeni halka arz olabilir)\n\n"
            
        son_fiyat = df["Close"].iloc[-1]
        onceki_fiyat = df["Close"].iloc[-2]
        hacim_son = df["Volume"].iloc[-1]
        
        # Hacim ortalaması için mevcut veri kadar periyot kullan
        hacim_periyot = min(len(df), 10)
        hacim_ort = df["Volume"].tail(hacim_periyot).mean()
        
        degisim = ((son_fiyat - onceki_fiyat) / onceki_fiyat) * 100
        
        # Göstergeler (Veri uzunluğuna göre esnek hesaplama)
        rsi_val = None
        if len(df) >= 15:
            df["RSI"] = calculate_rsi(df["Close"], period=14)
            rsi_val = df["RSI"].iloc[-1]
            
        sma20_val = df["Close"].rolling(window=min(len(df), 20)).mean().iloc[-1]
        sma50_val = df["Close"].rolling(window=50).mean().iloc[-1] if len(df) >= 50 else None
        
        hacim_durum = "🔥 Yüksek Hacim" if hacim_son > (hacim_ort * 1.3) else "💤 Normal Hacim"
        
        # Yön ve Tahmin Algoritması (Öncelik RSI ve Aşırı Satım/Alım Tepkisi)
        if rsi_val is not None and rsi_val < 30:
            tahmin = "🚀 AŞIRI SATIM (Tepki Yükselişi / AL Sinyali Potansiyeli)"
        elif rsi_val is not None and rsi_val > 70:
            tahmin = "⚠️ AŞIRI ALIM (Kar Satışı / Düzeltme Riski)"
        elif son_fiyat > sma20_val and (sma50_val is None or sma20_val > sma50_val):
            tahmin = "📈 YÜKSELİŞ TRENDİ DEVAM EDİYOR"
        elif son_fiyat > sma20_val:
            tahmin = "↗️ KISA VADELİ POZİTİF SEYİR"
        elif son_fiyat < sma20_val:
            tahmin = "📉 DÜŞÜŞ BASKISI VAR"
        else:
            tahmin = "🟡 NÖTR / YATAY SEYİR"
            
        rsi_str = f"{rsi_val:.1f}" if rsi_val is not None else "Yetersiz Veri"
        
        out = f"🔹 **{symbol}**: {son_fiyat:.2f} TL (%{degisim:+.2f})\n"
        out += f"   • RSI(14): {rsi_str}\n"
        out += f"   • Hacim: {hacim_durum}\n"
        out += f"   • Tahmin: {tahmin}\n\n"
        return out
        
    except Exception as e:
        return f"❌ {symbol} çekilemedi: {e}\n\n"

if __name__ == "__main__":
    analiz_ve_tahmin_yap()
