import os
import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# 1. 初始化 Gemini 用戶端 (已直接填入您的 API Key)
api_key = "AIzaSyBQS1AgANH1cyAbLV1o1otNUXpb8FvleEU"
client = genai.Client(api_key=api_key)

# 2. 設定網頁版面 (針對手機優化：移除 wide 模式，使用適合直式螢幕的 centered)
st.set_page_config(layout="centered", page_title="Mobile Stock Monitor")
st.title("📱 華爾街行動自訂監控面板")

# 3. 側邊欄設定：支援多支股票輸入
st.sidebar.header("控制台 | Settings")
default_stocks = "4966, 0050, 00919, NVDA, AAPL"
raw_input = st.sidebar.text_area("輸入股票代碼 (用逗號隔開):", value=default_stocks, height=120)

# 處理代碼字串轉換
ticker_list = [t.strip().upper() for t in raw_input.split(",") if t.strip()]

# 手動同步按鈕 (放置於側邊欄)
if st.sidebar.button("🔄 同步更新全部數據"):
    st.cache_data.clear()
    st.rerun()

# 【核心結構】結構化 JSON 輸出格式
class StockAnalysisSchema(BaseModel):
    rating: str = Field(description="投資評級，只能是 '買入 (Buy)', '持有 (Hold)', 或 '賣出 (Sell)' 之一")
    reason: str = Field(description="15字以內的一句話專業買方核心邏輯支撐")

# 4. 核心處理函式
@st.cache_data(ttl=120)
def fetch_and_analyze(ticker_name):
    formatted = ticker_name
    if formatted.isdigit():
        formatted = f"{formatted}.TW"
        
    try:
        stock = yf.Ticker(formatted)
        info = stock.info
        hist = stock.history(period="1mo")
        
        current_price = info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))
        day_high = info.get('dayHigh', 'N/A')
        day_low = info.get('dayLow', 'N/A')
        volume = info.get('volume', 'N/A')
        recent_trend = hist['Close'].tail(5).tolist() if not hist.empty else []
        
        prompt = f"""
        你是一位擁有20年經驗的華爾街資深買方股票分析師。
        請根據以下標的 {ticker_name} 的即時市場數據進行快速評級：
        - 現價: {current_price}
        - 52週高低: {info.get('fiftyTwoWeekHigh')} / {info.get('fiftyTwoWeekLow')}
        - 近5日走勢: {recent_trend}
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=StockAnalysisSchema,
                temperature=0.2
            ),
        )
        
        import json
        ai_data = json.loads(response.text)
        
        return {
            "success": True,
            "ticker": ticker_name,
            "price": current_price,
            "high": day_high,
            "low": day_low,
            "volume": volume,
            "rating": ai_data.get("rating", "持有 (Hold)"),
            "reason": ai_data.get("reason", "觀望中")
        }
    except Exception as e:
        return {"success": False, "ticker": ticker_name, "error": str(e)}

# 5. 主畫面手機版卡片渲染 (不使用橫向大表格，改用垂直區塊，手機更好滑)
progress_bar = st.progress(0)
total_stocks = len(ticker_list)

for index, t in enumerate(ticker_list):
    res = fetch_and_analyze(t)
    
    # 使用 st.container 打造獨立的「股票卡片」
    with st.container():
        if res["success"]:
            # 第一行：代碼與價格
            p = res['price']
            price_str = f"${p:.2f}" if isinstance(p, (int, float)) else f"{p}"
            
            # 建立左右兩欄，左邊是代碼，右邊是價格與評級
            c1, c2 = st.columns([1, 1])
            c1.markdown(f"### 📈 {res['ticker']}")
            
            rating_str = res['rating']
            if "買" in rating_str or "Buy" in rating_str:
                c2.markdown(f"### <span style='color:#28a745;'>🟢 {rating_str}</span>", unsafe_allow_html=True)
            elif "賣" in rating_str or "Sell" in rating_str:
                c2.markdown(f"### <span style='color:#dc3545;'>🔴 {rating_str}</span>", unsafe_allow_html=True)
            else:
                c2.markdown(f"### <span style='color:#ffc107;'>🟡 {rating_str}</span>", unsafe_allow_html=True)
            
            # 第二行：即時數據資訊
            v = res['volume']
            vol_str = f"{v:,}" if isinstance(v, (int, float)) else f"{v}"
            st.markdown(f"**現價：** {price_str} | **高/低：** {res['high']}/{res['low']} | **量：** {vol_str}")
            
            # 第三行：AI 觀點
            st.markdown(f"> 💬 **買方觀點：** {res['reason']}")
        else:
            st.error(f"❌ 股票代碼 {t} 獲取失敗，請檢查格式。")
            
        # 卡片底部分隔線
        st.markdown("<hr style='margin:10px 0px; opacity:0.3;'>", unsafe_allow_html=True)
    
    progress_bar.progress((index + 1) / total_stocks)

progress_bar.empty()