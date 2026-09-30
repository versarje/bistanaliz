import os
import requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series, fast=12, slow=26, signal=9):
    exp1 = series.ewm(span=fast, adjust=False).mean()
    exp2 = series.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def calculate_bollinger(series, window=20, std_dev=2):
    sma = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    return upper_band, lower_band

def get_bist_data_zero(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.IS?range=6mo&interval=1d"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
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

def get_fundamental_data(symbol):
    """Yeni tahtalar için Temel Analiz Çarpanlarını (F/K, PD/DD) Çeker"""
    try:
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}.IS?modules=summaryDetail,defaultKeyStatistics"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10).json()
        
        result = res['quoteSummary']['result'][0]
        summary = result.get('summaryDetail', {})
        stats = result.get('defaultKeyStatistics', {})
        
        fk = summary.get('trailingPE', {}).get('fmt', 'N/A')
        pddd = stats.get('priceToBook', {}).get('fmt', 'N/A')
        
        return f"F/K: {fk} | PD/DD: {pddd}"
    except:
        return "F/K: N/A | PD/DD: N/A"

def get_kap_news(symbol):
    """Yeni tahtalar için KAP/Şirket Haber Akışını Süzme"""
    try:
        url = f"https://news.google.com/rss/search?q={symbol}+BIST+KAP+veya+iş+anlaşması&hl=tr&gl=TR&ceid=TR:tr"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.content, 'xml')
        items = soup.find_all('item', limit=1)
        
        if items and items[0].title:
            title = items[0].title.text.strip()
            # Başlıktan gazete adlarını temizleme
            if " - " in title:
                title = title.split(" - ")[0]
            return title
        return "Son dönemde öne çıkan kritik KAP/Sözleşme haberi yok."
    except:
        return "Haber akışı taranıyor..."

def get_bist100_trend():
    try:
        df = get_bist_data_zero("XU100")
        if df.empty:
            return "Piyasa Yönü Belirsiz 🟡"
        son_fiyat = df["Close"].iloc[-1]
        sma20 = df["Close"].rolling(window=20).mean().iloc[-1]
        return "Borsa Olumlu (Yükseliş Trendi) 🟢" if son_fiyat > sma20 else "Borsa Olumsuz (Düşüş Baskısı) 🔴"
    except:
        return "Piyasa Yönü Belirsiz 🟡"

def get_bist_news_zero():
    try:
        url = "https://www.cnnturk.com/feed/rss/ekonomi/news"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.content, 'xml')
        items = soup.find_all('item', limit=3)
        headlines = [item.title.text.strip() for item in items if item.title]
        return headlines if headlines else ["Piyasa haber akışı şu an sakin."]
    except Exception as e:
        return ["Günün öne çıkan piyasa haberleri taranıyor..."]

def net_karar_ver(son_fiyat, sma20_val, sma50_val, macd_val, macd_sig, bollinger_alt, hacim_son, hacim_ort, degisim, xu100_durum, rsi_val):
    skor = 0.0
    if son_fiyat > sma20_val:
        skor += 1.0
    if sma50_val and sma20_val > sma50_val:
        skor += 1.0
    if macd_val is not None and macd_sig is not None and macd_val > macd_sig:
        skor += 1.0
    if bollinger_alt is not None and son_fiyat <= bollinger_alt:
        skor += 1.0
    if hacim_son > (hacim_ort * 1.3) and degisim > 0:
        skor += 0.5
    if "Olumlu" in xu100_durum:
        skor += 0.5

    if rsi_val is not None and rsi_val <= 30:
        return "🚀 GÜÇLÜ AL (Aşırı Düşmüş, Tepki Yükselişi Bekleniyor)"
    elif rsi_val is not None and rsi_val >= 70:
        return "⚠️ SAT / DÜZELTME RİSKİ (Aşırı Şişmiş)"
    elif skor >= 3.5:
        return "🟢 AL (Yükseliş Trendinde)"
    elif skor >= 2.0:
        return "↗️ TUT / POZİTİF (Kazanım Korunabilir)"
    elif son_fiyat < sma20_val and (rsi_val is None or rsi_val < 45):
        return "🔴 SAT / UZAK DUR (Düşüş Trendinde)"
    else:
        return "🟡 BEKLE / NÖTR (Net Yön Yok)"

def hisse_analiz_et(symbol, xu100_durum, is_new_stock=False):
    try:
        df = get_bist_data_zero(symbol)
        
        if df.empty or len(df) < 15:
            return f"🔹 **{symbol}**: Veri bulunamadı.\n\n"
            
        son_fiyat = df["Close"].iloc[-1]
        dunku_fiyat = df["Close"].iloc[-2]
        
        degisim_1g = ((son_fiyat - dunku_fiyat) / dunku_fiyat) * 100
        
        if len(df) >= 11:
            fiyat_10g = df["Close"].iloc[-11]
            degisim_10g = ((son_fiyat - fiyat_10g) / fiyat_10g) * 100
            trend_10g = f"%{degisim_10g:+.2f}"
        else:
            trend_10g = "Yeni Tahta"
            
        hacim_son = df["Volume"].iloc[-1]
        hacim_ort = df["Volume"].tail(10).mean()
        
        df["RSI"] = calculate_rsi(df["Close"], period=14)
        sma20 = df["Close"].rolling(window=min(len(df), 20)).mean()
        sma50 = df["Close"].rolling(window=50).mean() if len(df) >= 50 else pd.Series([None]*len(df))
        upper_b, lower_b = calculate_bollinger(df["Close"])
        macd_l, macd_s = calculate_macd(df["Close"])
        
        karar_bugun = net_karar_ver(
            son_fiyat, sma20.iloc[-1], sma50.iloc[-1], macd_l.iloc[-1], macd_s.iloc[-1],
            lower_b.iloc[-1] if len(df)>=20 else None, hacim_son, hacim_ort, degisim_1g, xu100_durum, df["RSI"].iloc[-1]
        )
        
        degisim_dun = ((dunku_fiyat - df["Close"].iloc[-3]) / df["Close"].iloc[-3]) * 100 if len(df)>=3 else 0
        karar_dun = net_karar_ver(
            dunku_fiyat, sma20.iloc[-2], sma50.iloc[-2], macd_l.iloc[-2], macd_s.iloc[-2],
            lower_b.iloc[-2] if len(df)>=21 else None, df["Volume"].iloc[-2], hacim_ort, degisim_dun, xu100_durum, df["RSI"].iloc[-2]
        )
        
        out = f"🔹 **{symbol}**: {son_fiyat:.2f} TL (%{degisim_1g:+.2f})\n"
        out += f"   • **Bugünkü Karar:** {karar_bugun}\n"
        out += f"   • **Dünkü Karar:** {karar_dun}\n"
        out += f"   • **10 Günlük Trend:** {trend_10g}\n"
        
        # Sadece 50+ Günü Geçmiş Yeni Tahtalar İçin Özel Detaylar
        if is_new_stock:
            temel_veri = get_fundamental_data(symbol)
            kap_haberi = get_kap_news(symbol)
            out += f"   • **📊 Çarpanlar:** {temel_veri}\n"
            out += f"   • **📣 KAP/Şirket Haberi:** {kap_haberi}\n"
            
        out += "\n"
        return out
        
    except Exception as e:
        return f"❌ {symbol} çekilemedi: {e}\n\n"

def analiz_ve_tahmin_yap():
    ana_hisseler = ["THYAO", "GARAN", "EREGL", "ASELS", "TUPRS", "KCHOL"]
    halka_arzlar = ["KARCL", "MASFN", "METEN", "SSAAT", "SARAE", "ALBTN"]
    
    xu100_durum = get_bist100_trend()
    
    rapor = "📊 **BİST AL / SAT SİNYAL & DERİN ANALİZ RAPORU** 📊\n"
    rapor += f"🏛 **Genel Borsa Durumu:** {xu100_durum}\n\n"
    
    rapor += "📈 **KÖKLÜ BİST HİSSELERİ (SADE TAHMİN)**\n"
    for symbol in ana_hisseler:
        rapor += hisse_analiz_et(symbol, xu100_durum, is_new_stock=False)
        
    rapor += "🆕 **YENİ HALKA ARZ TAHTALARI (TEMEL & KAP ANALİZLİ)**\n"
    for symbol in halka_arzlar:
        rapor += hisse_analiz_et(symbol, xu100_durum, is_new_stock=True)
            
    rapor += "📰 **ÖNE ÇIKAN BİST HABERLERİ**\n"
    haberler = get_bist_news_zero()
    for h in haberler:
        rapor += f"• {h}\n"
        
    print(rapor)
    
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": rapor, "parse_mode": "Markdown"})

if __name__ == "__main__":
    analiz_ve_tahmin_yap()
