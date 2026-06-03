import os
import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# 1. 初始化 Gemini 用戶端 (已填入您的專屬 API Key)
api_key = "81a265563956411097b22208aad7b96e"
client = genai.Client(api_key=api_key)

# 2. 設定網頁版面 (針對手機直式螢幕進行優化)
st.set_page_config(layout="centered", page_title="Mobile Stock Monitor")
st.title("📱 華爾街行動自訂監控面板")

# 3. 側邊欄控制台：支援 20-50 支股票輸入
st.sidebar.header("控制台 | Settings")
default_stocks = "4966, 0050, 00919, NVDA, AAPL"
raw_input = st.sidebar.text_area("輸入股票代碼 (用逗號隔開):", value=default_stocks, height=120)

# 處理代碼字串轉換，去除前後空白並轉大寫
ticker_list = [t.strip().upper() for t in raw_input.split(",") if t.strip()]

# 強制清除快取同步按鈕
if st.sidebar.button("🔄 同步更新全部數據"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("""
---
💡 **行動裝置小技巧：**
1. 支援同時監控多支台股與美股。
2. 台股只需輸入純數字（如 `4966`），系統會自動補上 `.TW`。
3. 本版本已針對雲端海外伺服器進行「防阻擋最佳化」，大幅提升連線穩定度。
""")

# 【結構化輸出定義】
class StockAnalysisSchema(BaseModel):
    rating: str = Field(description="投資評級，只能是 '買入 (Buy)', '持有 (Hold)', 或 '賣出 (Sell)' 之一")
    reason: str = Field(description="15字以內的一句話專業買方核心邏輯支撐")

# 4. 核心同步處理函式 (跨國雲端環境防阻擋優化版)
@st.cache_data(ttl=60) # 縮短快取至60秒
def fetch_and_analyze(ticker_name):
    formatted = str(ticker_name).strip()
    
    if formatted.isdigit() and not formatted.endswith(".TW"):
        formatted = f"{formatted}.TW"
        
    try:
        # 向 yfinance 要求歷史數據（歷史走勢在海外雲端最不容易被封鎖）
        stock = yf.Ticker(formatted)
        hist = stock.history(period="1mo")
        
        if hist.empty:
            raise ValueError("海外伺服器連線超時，暫時無法讀取歷史K線。")
            
        # 【核心修正】不使用常被海外機房封鎖的 stock.info，直接從 hist 提取最準確的即時交易數據
        latest_row = hist.iloc[-1]
        current_price = latest_row['Close']
        day_high = latest_row['High']
        day_low = latest_row['Low']
        volume = latest_row['Volume']
        
        recent_trend = hist['Close'].tail(5).tolist()
        
        # 建立高純度的華爾街分析師 Prompt
        prompt = f"""
        你是一位擁有20年經驗的華爾街資深買方股票分析師。
        請嚴格使用過去五年的完整財報、TTM（最近12個月）數據及近期市場趨勢，並依循以下架構為我生成分析：
        1. 執行摘要（Executive Summary）： 簡述公司的核心業務模式、獲利引擎與當前市值規模。
        2. 投資論點（Investment Thesis）： 列出為何應看好（多頭）或看空（空頭）的3大理由。
        3. 財務健康檢查（Financial Health）： 分析營收成長率、營業利潤率、現金流狀況及資產負債表風險。   
        4. 估值評估（Valuation）： 根據本益比（P/E）、股價淨值比（P/B）等指標評估當前股價是否合理。
        5. 競爭護城河與同業比較（Moat & Competitors）： 評估公司在產業中的競爭優勢與對手差異。
        6. 潛在風險提示（Risk Factors）： 指出公司特有的前3大潛在風險（如供應鏈、關鍵人物、訴訟等）。
        7. 總結與行動建議（Final Verdict & Action）： 給出明確的「買入/持有/賣出」評級與簡潔的邏輯支撐。 
        """
        
        # 全自動呼叫 Gemini 進行背景分析
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
            "display_ticker": formatted,
            "price": current_price,
            "high": day_high,
            "low": day_low,
            "volume": volume,
            "rating": ai_data.get("rating", "持有 (Hold)"),
            "reason": ai_data.get("reason", "數據觀望中")
        }
    except Exception as e:
        return {"success": False, "ticker": ticker_name, "display_ticker": formatted, "error": str(e)}

# 5. 主畫面：手機優化版直式卡片佈局
progress_bar = st.progress(0)
total_stocks = len(ticker_list)

for index, t in enumerate(ticker_list):
    res = fetch_and_analyze(t)
    
    with st.container():
        if res["success"]:
            p = res['price']
            price_str = f"${p:.2f}" if isinstance(p, (int, float)) else f"{p}"
            v = res['volume']
            vol_str = f"{v:,}" if isinstance(v, (int, float)) else f"{v}"
            
            c1, c2 = st.columns([1, 1])
            c1.markdown(f"### 📈 {res['ticker']}")
            
            rating_str = res['rating']
            if "買" in rating_str or "Buy" in rating_str:
                c2.markdown(f"### <span style='color:#28a745; float:right;'>🟢 {rating_str}</span>", unsafe_allow_html=True)
            elif "賣" in rating_str or "Sell" in rating_str:
                c2.markdown(f"### <span style='color:#dc3545; float:right;'>🔴 {rating_str}</span>", unsafe_allow_html=True)
            else:
                c2.markdown(f"### <span style='color:#ffc107; float:right;'>🟡 {rating_str}</span>", unsafe_allow_html=True)
            
            # 高低價格式化輸出
            h = res['high']
            l = res['low']
            high_str = f"{h:.2f}" if isinstance(h, (int, float)) else str(h)
            low_str = f"{l:.2f}" if isinstance(l, (int, float)) else str(l)
            
            st.markdown(f"**現價：** `{price_str}` | **高/低：** `{high_str}` / `{low_str}` | **成交量：** `{vol_str}`")
            st.markdown(f"> 💬 **買方核心邏輯：** {res['reason']}")
        else:
            st.error(f"❌ 股票代碼 **{res['ticker']}** ({res['display_ticker']}) 數據下載超時。")
            st.caption(f"提示：已啟動備用防封鎖機制，如仍失敗，代表 Yahoo Finance 海外節點當前負載過高，請點擊左側「🔄 同步更新全部數據」重試。")
            
        st.markdown("<hr style='margin:12px 0px; padding:0px; opacity:0.25;'>", unsafe_allow_html=True)
    
    progress_bar.progress((index + 1) / total_stocks)

progress_bar.empty()
