import os
import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import json
import time
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
default_stocks = "4966, 0050, 鴻海, NVDA, TSLA, 輝達"
raw_input = st.sidebar.text_area("輸入股票代碼或中文名稱 (用逗號隔開):", value=default_stocks, height=120)

# 處理代碼字串轉換，去除前後空白
raw_ticker_list = [t.strip() for t in raw_input.split(",") if t.strip()]

if st.sidebar.button("🔄 同步更新全部數據"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("""
---
💡 **行動裝置高級技巧：**
1. **輸入極具彈性**：支援輸入純數字 (`0050`)、美股代碼 (`AAPL`)、或直接輸入中文名稱 (`鴻海`、`輝達`)。
2. **內置技術分析線圖**：每一張卡片自動渲染「日線軌跡」與「布林通道（20MA ± 2σ）」。
3. **結論後置**：評級完全建立在 AI 完成 7 大面向深度報告的基礎上。
""")

# 【核心結構 1】前段分析：基本面與估值
class Part1Report(BaseModel):
    ticker: str
    executive_summary: str = Field(description="執行摘要：簡述核心業務模式、獲利引擎與當前市值規模")
    investment_thesis: str = Field(description="投資論點：列出為何應看好或看空的3大理由")
    financial_health: str = Field(description="財務健康檢查：分析營收成長、利潤率與現金流狀況")
    valuation: str = Field(description="估值評估：根據本益比、股價淨值比等指標評估當前股價")

class BatchPart1Schema(BaseModel):
    reports: List[Part1Report]

# 【核心結構 2】後段分析：競爭力、風險與最終投資評級結論
class Part2Report(BaseModel):
    ticker: str
    moat_competitors: str = Field(description="競爭護城河與同業比較：評估在產業中的競爭優勢與對手差異")
    risk_factors: str = Field(description="潛在風險提示：指出公司特有的前3大潛在風險")
    final_verdict_rating: str = Field(description="投資結論，必須根據上述全面分析後得出，只能是 '買入 (Buy)', '持有 (Hold)', 或 '賣出 (Sell)' 之一")
    final_verdict_logic: str = Field(description="簡潔的行動建議與長短期操作邏輯支撐")

class BatchPart2Schema(BaseModel):
    reports: List[Part2Report]

# 【智慧搜尋引擎】中文名稱全自動識別轉股票代碼核心
def convert_chinese_to_ticker(session, name_str):
    if name_str.isdigit():
        return f"{name_str}.TW"
    # 若本身就是純英文字母代碼 (美股)，直接回傳
    if name_str.isalpha():
        return name_str
        
    # 如果包含中文，調用 Yahoo Finance Query API 進行跨國模糊搜尋
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={requests.utils.quote(name_str)}&quotesCount=1&newsCount=0"
        res = session.get(url, timeout=5)
        data = res.json()
        quotes = data.get("quotes", [])
        if quotes:
            return quotes[0].get("symbol", name_str)
    except:
        pass
    return name_str

# 智慧型雙階段單股救援機制
def analyze_single_stock_rescue(ticker_name, data_dict):
    try:
        p1_prompt = f"你是一位擁有20年經驗的華爾街資深買方股票分析師。請針對目標公司 {ticker_name} 撰寫前段分析：1.執行摘要, 2.投資論點, 3.財務健康, 4.估值評估。請嚴格使用中英文雙語填寫。數據：{json.dumps(data_dict)}"
        res1 = client.models.generate_content(
            model='gemini-2.5-flash', contents=p1_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=Part1Report, temperature=0.2)
        )
        d1 = json.loads(res1.text)
        
        time.sleep(1.5)
        
        p2_prompt = f"你是一位華爾街買方股票分析師。請針對目標公司 {ticker_name} 撰寫後段分析與最終結論：5.競爭護城河與比較, 6.潛在風險, 7.綜合投資結論與評級。請嚴格使用中英文雙語。已知前段數據為：{res1.text}"
        res2 = client.models.generate_content(
            model='gemini-2.5-flash', contents=p2_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=Part2Report, temperature=0.2)
        )
        d2 = json.loads(res2.text)
        
        return {"success": True, "data": {**d1, **d2}}
    except Exception as e:
        return {"success": False, "error": f"深度分析生成超時 ({str(e)})"}

# 4. 批次數據抓取與智慧分段深度分析核心
@st.cache_data(ttl=60)
def fetch_all_and_analyze_batch(tickers):
    market_data_batch = {}
    success_stocks = []
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    # 第一階段：解析代碼並快速抓取行情與歷史 K 線數據
    for original_name in tickers:
        formatted = convert_chinese_to_ticker(session, original_name)
            
        try:
            stock = yf.Ticker(formatted, session=session)
            # 為了布林代數曲線（20 MA），我們至少需要拉取 3 個月（3mo）的日線數據
            hist = stock.history(period="3mo")
            if hist.empty:
                continue
                
            # 獲取中文/英文官方全名
            long_name = stock.info.get('longName', original_name)
            
            # 計算布林代數曲線 (Bollinger Bands)
            hist['MA20'] = hist['Close'].rolling(window=20).mean()
            hist['STD20'] = hist['Close'].rolling(window=20).std()
            hist['UpperBand'] = hist['MA20'] + (hist['STD20'] * 2)
            hist['LowerBand'] = hist['MA20'] - (hist['STD20'] * 2)
            
            latest_row = hist.iloc[-1]
            
            # 保存市場行情數據
            market_data_batch[original_name] = {
                "display_name": f"{long_name} ({formatted})",
                "price": float(latest_row['Close']),
                "high": float(latest_row['High']),
                "low": float(latest_row['Low']),
                "volume": int(latest_row['Volume']),
                "history_df": hist[['Close', 'MA20', 'UpperBand', 'LowerBand']].tail(40).to_json() # 轉為 JSON 快取，只取最近 40 天畫圖手機版最漂亮
            }
            success_stocks.append(original_name)
        except:
            pass

    # 第二階段：智慧型分段 AI 深度解構 (只傳送核心趨勢，縮減 tokens 以完美防止 429 封鎖)
    ai_reports_dict = {}
    if success_stocks:
        try:
            # 建立一個極簡的數據集給 AI 分析，不要塞整張大 DataFrame 進去
            ai_input_pool = {k: {
                "name": v["display_name"], "price": v["price"], "high": v["high"], "low": v["low"]
            } for k, v in market_data_batch.items()}
            
            prompt1 = f"你是一位擁有20年經驗的華爾街資深買方股票分析師。請針對數據池中的每一家公司進行前段投資解構，包含：1.執行摘要, 2.投資論點, 3.財務健康檢查, 4.估值評估。請使用中英文雙語生成 reports 列表。數據池：{json.dumps(ai_input_pool, ensure_ascii=False)}"
            response1 = client.models.generate_content(
                model='gemini-2.5-flash', contents=prompt1,
                config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=BatchPart1Schema, temperature=0.2),
            )
            raw_p1 = json.loads(response1.text).get("reports", [])
            
            time.sleep(2.0) # 強制物理冷卻防止刷流量
            
            prompt2 = f"你是一位資深買方分析師。請根據剛才生成的上半部報告，繼續為這批公司完成下半部深度點評，包含：5.競爭護城河與同業比較, 6.潛在風險提示, 7.綜合投資評級結論與行動建議。請使用中英文雙語。上半部數據參考：{response1.text}"
            response2 = client.models.generate_content(
                model='gemini-2.5-flash', contents=prompt2,
                config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=BatchPart2Schema, temperature=0.2),
            )
            raw_p2 = json.loads(response2.text).get("reports", [])
            
            p1_dict = {item["ticker"]: item for item in raw_p1}
            p2_dict = {item["ticker"]: item for item in raw_p2}
            
            for s_ticker in success_stocks:
                if s_ticker in p1_dict and s_ticker in p2_dict:
                    ai_reports_dict[s_ticker] = {**p1_dict[s_ticker], **p2_dict[s_ticker]}
        except:
            pass

    # 第三階段：整合與嚴格狀態檢查
    final_output = {}
    for t in tickers:
        if t in market_data_batch:
            data = market_data_batch[t]
            
            if t not in ai_reports_dict:
                rescue_res = analyze_single_stock_rescue(t, {"name": data["display_name"], "price": data["price"]})
                if rescue_res["success"]:
                    final_output[t] = {
                        "state": "REPORT_COMPLETE", "display_name": data["display_name"],
                        "price": data["price"], "high": data["high"], "low": data["low"], "volume": data["volume"],
                        "history_df": data["history_df"], "report": rescue_res["data"]
                    }
                else:
                    final_output[t] = {
                        "state": "MARKET_DATA_ONLY", "display_name": data["display_name"],
                        "price": data["price"], "high": data["high"], "low": data["low"], "volume": data["volume"],
                        "history_df": data["history_df"], "error": rescue_res['error']
                    }
            else:
                final_output[t] = {
                    "state": "REPORT_COMPLETE", "display_name": data["display_name"],
                    "price": data["price"], "high": data["high"], "low": data["low"], "volume": data["volume"],
                    "history_df": data["history_df"], "report": ai_reports_dict[t]
                }
        else:
            final_output[t] = {"state": "FAILED", "error": f"找不到符合 '{t}' 的股票或行情數據下載失敗。"}
            
    return final_output

# 5. 主畫面手機優化直式面板渲染
with st.spinner("🕵️‍♂️ 華爾街資深分析師正在利用雙階段模型解構財報並計算布林軌道，請稍候..."):
    results = fetch_all_and_analyze_batch(raw_ticker_list)

for t in raw_ticker_list:
    res = results.get(t, {"state": "FAILED", "error": "未知錯誤"})
    
    with st.container():
        if res["state"] in ["REPORT_COMPLETE", "MARKET_DATA_ONLY"]:
            p = res['price']
            price_str = f"${p:.2f}" if isinstance(p, (int, float)) else f"{p}"
            v = res['volume']
            vol_str = f"{v:,}" if isinstance(v, (int, float)) else f"{v}"
            
            # 🌟 亮點一：投資標的同步顯示代碼與中文官方全名
            st.markdown(f"## 🏢 {res['display_name']}")
            st.markdown(f"**即時現價：** `{price_str}` | **今日最高/最低：** `{res['high']:.2f}` / `{res['low']:.2f}` | **今日成交量：** `{vol_str}`")
            
            # 🌟 亮點二：全自動日線與布林代數曲線技術圖表 (Bollinger Bands Chart)
            try:
                chart_df = pd.read_json(res["history_df"])
                # 重新命名以便圖表標籤更乾淨專業
                chart_df.columns = ['收盤價 (Close)', '20日均線 (MA20)', '布林上軌 (Upper Band)', '布林下軌 (Lower Band)']
                st.line_chart(chart_df, height=220) # 220高最符合手機直式滑動視覺
            except Exception as chart_err:
                st.caption(f"技術圖表渲染暫時超載: {chart_err}")

            # 🌟 亮點三：嚴格合規 — 只有當 7 大面向完美生成，才吐出最終 conclusions 評級看板
            if res["state"] == "REPORT_COMPLETE":
                report_data = res["report"]
                rating_str = report_data.get("final_verdict_rating", "Not Rated")
                if "買" in rating_str or "Buy" in rating_str:
                    st.success(f"🎯 **機構綜合投資結論 (Final Verdict Rating)：{rating_str}**")
                elif "賣" in rating_str or "Sell" in rating_str:
                    st.error(f"🎯 **機構綜合投資結論 (Final Verdict Rating)：{rating_str}**")
                else:
                    st.warning(f"🎯 **機構綜合投資結論 (Final Verdict Rating)：{rating_str}**")
                    
                # 手機版折疊式深度報告手風琴
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
                    
                with st.expander("📢 7. 總結與行動建議 (Action)"):
                    st.info(f"**核心操作邏輯支撑：**\n{report_data.get('final_verdict_logic')}")
            else:
                # MARKET_DATA_ONLY 情況：有圖、有行情，但無結論（因 429 冷卻懲罰中）
                st.warning(f"⚠️ **無法給予 conclusions**：{res['error']}。")
                st.caption("提示：由於 Google 流量管制，此標的暫無 conclusions 看板。請等待 30 秒後，點擊左側「🔄 同步更新全部數據」重新嘗試數據解構。")
        
        else:
            # 基礎行情完全失敗
            st.error(f"❌ 股票標的 **{t}** 基礎行情載入失敗。")
            st.caption(f"原因提示：{res.get('error')}")
            
        st.markdown("<br><hr style='margin:15px 0px; border-top: 2px dashed opacity:0.3;'>", unsafe_allow_html=True)
