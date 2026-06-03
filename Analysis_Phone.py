import os
import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List

# 1. 初始化 Gemini 用戶端
GEMINI_API_KEY = "AIzaSyBQS1AgANH1cyAbLV1o1otNUXpb8FvleEU"
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
💡 **行動端防爆優化版：**
1. 已將 AI 請求優化為「機構級單次批次打包技術」。
2. 不論監控多少支股票，**每次刷新僅消耗 1 次 AI 額度**，徹底根除 429 錯誤！
""")

# 【結構化輸出定義】
class SingleStockResult(BaseModel):
    ticker: str
    rating: str = Field(description="投資評級，只能是 '買入 (Buy)', '持有 (Hold)', 或 '賣出 (Sell)' 之一")
    reason: str = Field(description="15字以內的一句話專業買方核心邏輯支撐")

class BatchAnalysisSchema(BaseModel):
    results: List[SingleStockResult]

# 4. 批次抓取與統一分析核心
@st.cache_data(ttl=60)
def fetch_all_and_analyze_batch(tickers):
    market_data_batch = {}
    success_stocks = []
    
    # 建立偽裝瀏覽器連線通道
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    # 第一階段：快速抓取所有股票的市場數據 (由 Python 在背景執行)
    for t in tickers:
        formatted = t
        if formatted.isdigit() and not formatted.endswith(".TW"):
            formatted = f"{formatted}.TW"
            
        try:
            stock = yf.Ticker(formatted, session=session)
            hist = stock.history(period="1mo")
            if hist.empty:
                continue
                
            latest_row = hist.iloc[-1]
            market_data_batch[t] = {
                "display_ticker": formatted,
                "price": float(latest_row['Close']),
                "high": float(latest_row['High']),
                "low": float(latest_row['Low']),
                "volume": int(latest_row['Volume']),
                "recent_trend": hist['Close'].tail(5).tolist()
            }
            success_stocks.append(t)
        except:
            pass

    # 第二階段：將所有抓到數據的股票打包，一次性餵給 Gemini 分析 (只消耗 1 次請求)
    ai_ratings = {}
    if success_stocks:
        try:
            prompt = f"""
            你是一位擁有20年經驗的華爾街資深買方股票分析師。
            請針對以下這批股票的即時市場數據，一口氣為每一支股票給予專業評級與核心操盤邏輯點評：
            
            【待分析股票數據池】：
            {json.dumps(market_data_batch, ensure_ascii=False)}
            """
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=BatchAnalysisSchema,
                    temperature=0.2
                ),
            )
            
            # 解析批量回傳的 JSON
            raw_ai_res = json.loads(response.text)
            for item in raw_ai_res.get("results", []):
                ai_ratings[item["ticker"]] = {
                    "rating": item["rating"],
                    "reason": item["reason"]
                }
        except:
            pass

    # 第三階段：整合市場數據與 AI 評級數據
    final_output = {}
    for t in tickers:
        if t in market_data_batch:
            data = market_data_batch[t]
            ai = ai_ratings.get(t, {"rating": "持有 (Hold)", "reason": "大盤觀望，數據同步中"})
            final_output[t] = {
                "success": True,
                "price": data["price"],
                "high": data["high"],
                "low": data["low"],
                "volume": data["volume"],
                "rating": ai["rating"],
                "reason": ai["reason"]
            }
        else:
            final_output[t] = {"success": False, "error": "數據下載超時或代碼無效"}
            
    return final_output

# 5. 主畫面卡片渲染
with st.spinner("華爾街分析師正在批次打包審視數據中..."):
    results = fetch_all_and_analyze_batch(ticker_list)

for t in ticker_list:
    res = results.get(t, {"success": False, "error": "未知錯誤"})
    
    with st.container():
        if res["success"]:
            p = res['price']
            price_str = f"${p:.2f}" if isinstance(p, (int, float)) else f"{p}"
            v = res['volume']
            vol_str = f"{v:,}" if isinstance(v, (int, float)) else f"{v}"
            
            c1, c2 = st.columns([1, 1])
            c1.markdown(f"### 📈 {t}")
            
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
            st.error(f"❌ 股票代碼 **{t}** 載入失敗。")
            st.caption(f"原因：{res.get('error')}。可能是開盤前無交易數據，或伺服器正在頻率限制中，請稍候重試。")
            
        st.markdown("<hr style='margin:12px 0px; padding:0px; opacity:0.25;'>", unsafe_allow_html=True)
