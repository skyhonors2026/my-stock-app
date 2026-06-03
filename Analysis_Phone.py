import os
import streamlit as st
import pandas as pd
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from twelvedata import TDClient

# 1. 初始化金融數據與 Gemini API 用戶端
# 請在此處填入您專屬的 API Key
TWELVEDATA_API_KEY = "YOUR_TWELVEDATA_API_KEY" 
GEMINI_API_KEY = "AIzaSyBQS1AgANH1cyAbLV1o1otNUXpb8FvleEU"

td = TDClient(apikey=TWELVEDATA_API_KEY)
client = genai.Client(api_key=GEMINI_API_KEY)

# 2. 設定網頁版面 (針對手機直式螢幕優化)
st.set_page_config(layout="centered", page_title="Mobile Stock Monitor")
st.title("📱 華爾街行動自訂監控面板")

# 3. 側邊欄控制台
st.sidebar.header("控制台 | Settings")
default_stocks = "4966, 0050, 00919, NVDA, AAPL"
raw_input = st.sidebar.text_area("輸入股票代碼 (用逗號隔開):", value=default_stocks, height=120)

# 處理代碼字串轉換
ticker_list = [t.strip().upper() for t in raw_input.split(",") if t.strip()]

if st.sidebar.button("🔄 同步更新全部數據"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("""
---
💡 **行動裝置小技巧：**
1. 本版本已換裝「機構級專用 API 資料源」，徹底解決 yfinance 被海外雲端伺服器封鎖的問題。
2. 台股與美股代碼皆可無縫全自動辨識與評級。
""")

# 【結構化輸出定義】
class StockAnalysisSchema(BaseModel):
    rating: str = Field(description="投資評級，只能是 '買入 (Buy)', '持有 (Hold)', 或 '賣出 (Sell)' 之一")
    reason: str = Field(description="15字以內的一句話專業買方核心邏輯支撐")

# 4. 核心同步處理函式 (Twelvedata 機構級高穩定版)
@st.cache_data(ttl=60)
def fetch_and_analyze(ticker_name):
    formatted = str(ticker_name).strip()
    
    # 判斷台股並處理為國際通用交易所後綴
    if formatted.isdigit():
        # Twelvedata 辨識台灣股票需使用 .TW 格式
        formatted = f"{formatted}.TW"
        
    try:
        # 向 Twelvedata 發出即時報價與歷史 K 線請求
        ts = td.time_series(symbol=formatted, interval="1day", outputsize=5)
        candles = ts.as_pandas()
        
        if candles.empty:
            raise ValueError("此股票代碼在當前市場無效或未開盤。")
            
        # 提取最新一筆收盤資訊
        latest_data = candles.iloc[0] # DataFrame 預設最新一天在最上面
        current_price = float(latest_data['close'])
        day_high = float(latest_data['high'])
        day_low = float(latest_data['low'])
        volume = int(latest_data['volume'])
        
        recent_trend = candles['close'].head(5).tolist()
        
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
            
            st.markdown(f"**現價：** `{price_str}` | **高/低：** `{res['high']:.2f}` / `{res['low']:.2f}` | **成交量：** `{vol_str}`")
            st.markdown(f"> 💬 **買方核心邏輯：** {res['reason']}")
        else:
            st.error(f"❌ 股票代碼 **{res['ticker']}** ({res['display_ticker']}) 載入失敗。")
            st.caption(f"錯誤原因：{res.get('error', '未知')}。請確認代碼或檢查 Twelvedata API Key 是否正確輸入。")
            
        st.markdown("<hr style='margin:12px 0px; padding:0px; opacity:0.25;'>", unsafe_allow_html=True)
    
    progress_bar.progress((index + 1) / total_stocks)

progress_bar.empty()
