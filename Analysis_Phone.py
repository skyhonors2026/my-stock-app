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

# 1. 初始化 Gemini 用戶端 (使用您的專屬有效金鑰)
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
💡 **買方嚴謹合規版：**
1. **結論後置機制**：投資評級（Rating）完全建立在 AI 對七大面向財報與市場深度解構的基礎上。
2. 若數據超時或 AI 未完成分析，系統絕不盲目給予任何預設評級，確保報告的專業與客觀性。
""")

# 【核心架構】定義完整的七大面向深度報告 JSON Schema
class DeepStockReport(BaseModel):
    ticker: str
    executive_summary: str = Field(description="執行摘要：簡述核心業務模式、獲利引擎與當前市值規模")
    investment_thesis: str = Field(description="投資論點：列出為何應看好（多頭）或看空（空頭）的3大理由")
    financial_health: str = Field(description="財務健康檢查：分析營收成長率、營業利潤率、現金流狀況及資產負債表風險")
    valuation: str = Field(description="估值評估：根據本益比、股價淨值比等指標評估當前股價是否合理")
    moat_competitors: str = Field(description="競爭護城河與同業比較：評估在產業中的競爭優勢與對手差異")
    risk_factors: str = Field(description="潛在風險提示：指出公司特有的前3大潛在風險")
    final_verdict_rating: str = Field(description="投資評級，必須根據上述全面分析後得出，且只能是 '買入 (Buy)', '持有 (Hold)', 或 '賣出 (Sell)' 之一")
    final_verdict_logic: str = Field(description="簡潔的行動建議與長短期操作邏輯支撐")

class BatchDeepAnalysisSchema(BaseModel):
    reports: List[DeepStockReport]

# 核心單股補發救援函式 (當批次失敗時的救援機制)
def analyze_single_stock_rescue(ticker_name, data_dict):
    try:
        prompt = f"你是一位擁有20年經驗的華爾街資深買方股票分析師。請針對目標公司 {ticker_name} 的即時數據進行全面、深度且客觀的綜合投資分析報告。請嚴格使用中英文雙語（Bilingual Traditional Chinese & English）填寫每一個欄位。數據：{json.dumps(data_dict)}"
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DeepStockReport,
                temperature=0.2
            ),
        )
        return {"success": True, "data": json.loads(response.text)}
    except Exception as e:
        return {"success": False, "error": str(e)}

# 4. 批次數據抓取與統一深度分析核心
@st.cache_data(ttl=60)
def fetch_all_and_analyze_batch(tickers):
    market_data_batch = {}
    success_stocks = []
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    # 第一階段：快速抓取所有股票的市場數據
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

    # 第二階段：打包丟給 Gemini 進行全自動深度報告生成
    ai_reports_dict = {}
    if success_stocks:
        try:
            prompt = f"你是一位擁有20年經驗的華爾街資深買方股票分析師。請針對待分析池中的每一家目標公司進行全面、客觀且極度深入的綜合投資分析報告。請嚴格結合所提供的數據，並使用中英文雙語為每一家公司生成完整的 reports 清單。數據池：{json.dumps(market_data_batch, ensure_ascii=False)}"
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=BatchDeepAnalysisSchema,
                    temperature=0.2
                ),
            )
            raw_ai_res = json.loads(response.text)
            for r in raw_ai_res.get("reports", []):
                ai_reports_dict[r["ticker"]] = r
        except:
            pass

    # 第三階段：整合與嚴格合規檢查（無報告就無評級）
    final_output = {}
    for t in tickers:
        if t in market_data_batch:
            data = market_data_batch[t]
            
            # 若批次漏掉，立刻啟動救援補發
            if t not in ai_reports_dict:
                rescue_res = analyze_single_stock_rescue(t, data)
                if rescue_res["success"]:
                    final_output[t] = {
                        "state": "SUCCESS_WITH_REPORT",
                        "price": data["price"], "high": data["high"], "low": data["low"], "volume": data["volume"],
                        "report": rescue_res["data"]
                    }
                else:
                    final_output[t] = {
                        "state": "DATA_ONLY",
                        "price": data["price"], "high": data["high"], "low": data["low"], "volume": data["volume"],
                        "error": f"AI 深度解構超時 ({rescue_res['error']})"
                    }
            else:
                final_output[t] = {
                    "state": "SUCCESS_WITH_REPORT",
                    "price": data["price"], "high": data["high"], "low": data["low"], "volume": data["volume"],
                    "report": ai_reports_dict[t]
                }
        else:
            final_output[t] = {"state": "FAILED", "error": "基礎行情數據下載超時，海外伺服器連線異常。"}
            
    return final_output

# 5. 主畫面手機優化直式面板渲染
with st.spinner("🕵️‍♂️ 華爾街資深分析師正在全面解構財報與市場走勢，請稍候..."):
    results = fetch_all_and_analyze_batch(ticker_list)

for t in ticker_list:
    res = results.get(t, {"state": "FAILED", "error": "未知錯誤"})
    
    with st.container():
        # 情況 A：行情與 AI 報告皆成功獲取（完美渲染）
        if res["state"] == "SUCCESS_WITH_REPORT":
            p = res['price']
            price_str = f"${p:.2f}" if isinstance(p, (int, float)) else f"{p}"
            v = res['volume']
            vol_str = f"{v:,}" if isinstance(v, (int, float)) else f"{v}"
            
            st.markdown(f"## 🏢 投資標的：{t}")
            st.markdown(f"**即時現價：** `{price_str}` | **今日最高/最低：** `{res['high']:.2f}` / `{res['low']:.2f}` | **今日成交量：** `{vol_str}`")
            
            report_data = res["report"]
            
            # 🌟 嚴格合規：投資評級完全建立在七大面向報告成功生成的基礎上！
            rating_str = report_data.get("final_verdict_rating", "未評級")
            if "買" in rating_str or "Buy" in rating_str:
                st.success(f"🎯 **機構綜合投資評級 (Final Rating)：{rating_str}**")
            elif "賣" in rating_str or "Sell" in rating_str:
                st.error(f"🎯 **機構綜合投資評級 (Final Rating)：{rating_str}**")
            else:
                st.warning(f"🎯 **機構綜合投資評級 (Final Rating)：{rating_str}**")
                
            # 手機版折疊式深度報告選單
            with st.expander("🔍 1. 執行摘要 (Executive Summary)"):
                st.write(report_data.get("executive_summary"))
                
            with st.expander("⚡ 2. 投資論點 (Investment Thesis)"):
                st.write(report_data.get("investment_thesis"))
                
            with st.expander("🩺 3. 財務健康檢查 (Financial Health)"):
                st.write(report_data.get("financial_health"))
                
            with st.expander("⚖️ 4. 估值評估 (Valuation)"):
                st.write(report_data.get("valuation"))
                
            with st.expander("🛡️ 5. 競爭護城河與同業比較 (Moat & Competitors)"):
                st.write(report_data.get("moat_competitors"))
                
            with st.expander("🚨 6. 潛在風險提示 (Risk Factors)"):
                st.write(report_data.get("risk_factors"))
                
            with st.expander("📢 7. 總結與行動建議 (Final Verdict & Action)"):
                st.info(f"**核心操作邏輯支撑：**\n{report_data.get('final_verdict_logic')}")
        
        # 情況 B：只有抓到行情數據，但 AI 分析當前失敗（絕不預設任何評級，只展現行情與提示）
        elif res["state"] == "DATA_ONLY":
            p = res['price']
            price_str = f"${p:.2f}" if isinstance(p, (int, float)) else f"{p}"
            st.markdown(f"## 🏢 投資標的：{t}")
            st.markdown(f"**即時現價：** `{price_str}` | **今日最高/最低：** `{res['high']:.2f}` / `{res['low']:.2f}`")
            st.warning(f"⚠️ **無法給予評級**：{res['error']}。請點擊左側「🔄 同步更新全部數據」嘗試為該股重新補發 AI 分析。")
            
        # 情況 C：完全下載失敗
        else:
            st.error(f"❌ 股票代碼 **{t}** 基礎行情下載失敗。")
            st.caption(f"原因提示：{res.get('error')}")
            
        # 卡片底部分隔線
        st.markdown("<br><hr style='margin:15px 0px; border-top: 2px dashed opacity:0.3;'>", unsafe_allow_html=True)
