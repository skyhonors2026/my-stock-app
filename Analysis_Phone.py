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
default_stocks = "00919, 0050, 2454, 2330, 3592, 4961, 2303, 4966, 元大, 緯創"
raw_input = st.sidebar.text_area("輸入股票代碼或中文名稱 (用逗號隔開):", value=default_stocks, height=120)

# 處理代碼字串轉換，去除前後空白
raw_ticker_list = [t.strip() for t in raw_input.split(",") if t.strip()]

if st.sidebar.button("🔄 同步更新全部數據"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("""
---
💡 **行動裝置高級技巧：**
1. **中英代碼智慧翻譯**：已全面升級內置精準對照表，支援 `元大`、`緯創` 等中文秒級翻譯。
2. **反封鎖瀏覽器核心**：升級真人類比標頭，徹底穿透 Yahoo 對雲端海外機房的阻擋。
3. **結論後置**：評級完全建立在 AI 完成 7 大面向深度報告的基礎上。
""")

# 【核心結構 1】前段分析：基本面與估值
class Part1Report(BaseModel):
    ticker: str
    executive_summary: str = Field(description="執行摘要：簡述核心業務模式、獲利引擎與當前市值規模")
    investment_thesis: str = Field(description="投資論點：列出為何應看好或看空的3大理由")
    financial_health: str = Field(description="財務健康檢查：分析營收成長、利潤率與現金流狀況")
    valuation: str = Field(description="估值評估：根據本益比等指標評估當前股價")

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

# 【擴充版：智慧硬核對照表】包含您輸入的新個股與常見權值股，100% 繞過 Yahoo 模糊搜尋限制
COMMON_STOCK_MAP = {
    "鴻海": "2317.TW", "台積電": "2330.TW", "聯發科": "2454.TW", "富邦金": "2881.TW",
    "國泰金": "2882.TW", "中信金": "2891.TW", "元大台灣50": "0050.TW", "元大": "0050.TW", 
    "元大高股息": "0056.TW", "群益台灣精選高息": "00919.TW", "聯電": "2303.TW",
    "緯創": "3231.TW", "譜瑞": "4966.TW", "天鈺": "4961.TW", "新普": "3592.TW",
    "輝達": "NVDA", "特斯拉": "TSLA", "蘋果": "AAPL", "微軟": "MSFT", "谷歌": "GOOGL"
}

def convert_chinese_to_ticker(session, name_str):
    if name_str in COMMON_STOCK_MAP:
        return COMMON_STOCK_MAP[name_str]
    if name_str.isdigit():
        return f"{name_str}.TW"
    if name_str.isalpha():
        return name_str
        
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={requests.utils.quote(name_str)}&quotesCount=1&newsCount=0"
        res = session.get(url, timeout=5)
        quotes = res.json().get("quotes", [])
        if quotes:
            return quotes[0].get("symbol", name_str)
    except:
        pass
    return name_str

# 智慧型雙階段單股救援機制
def analyze_single_stock_rescue(ticker_name, data_dict):
    try:
        p1_prompt = f"你是一位擁有20年經驗的華爾街資深買方股票分析師。請針對目標公司 {ticker_name} 撰寫前段分析：1.執行摘要, 2.投資論點, 3.財務健康, 4.估值評估。請完全使用繁體中文填寫。數據：{json.dumps(data_dict)}"
        res1 = client.models.generate_content(
            model='gemini-2.5-flash', contents=p1_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=Part1Report, temperature=0.2)
        )
        d1 = json.loads(res1.text)
        time.sleep(1.5)
        
        p2_prompt = f"你原是華爾街資深分析師。請針對目標公司 {ticker_name} 撰寫後段分析與最終結論：5.競爭護城河與比較, 6.潛在風險, 7.綜合投資結論與評級。請完全使用繁體中文填寫。已知前段數據為：{res1.text}"
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
    
    # 🔥【終極反阻擋核心】全面升級網頁特徵偽裝，包含完整的真人類別交握與語系要求
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })
    
    # 第一階段：快速抓取行情與歷史 K 線
    for original_name in tickers:
        formatted = convert_chinese_to_ticker(session, original_name)
            
        try:
            stock = yf.Ticker(formatted, session=session)
            hist = stock.history(period="3mo")
            if hist.empty:
                continue
                
            long_name = stock.info.get('longName', original_name)
            
            # 計算布林通道 (Bollinger Bands)
            hist['MA20'] = hist['Close'].rolling(window=20).mean()
            hist['STD20'] = hist['Close'].rolling(window=20).std()
            hist['UpperBand'] = hist['MA20'] + (hist['STD20'] * 2)
            hist['LowerBand'] = hist['MA20'] - (hist['STD20'] * 2)
            
            latest_row = hist.iloc[-1]
            
            plot_df = hist[['Close', 'MA20', 'UpperBand', 'LowerBand']].tail(40).copy()
            plot_df.index = plot_df.index.strftime('%Y-%m-%d')
            
            market_data_batch[original_name] = {
                "display_name": f"{long_name} ({formatted})",
                "price": float(latest_row['Close']),
                "high": float(latest_row['High']),
                "low": float(latest_row['Low']),
                "volume": int(latest_row['Volume']),
                "history_df": plot_df.to_json(orient='split')
            }
            success_stocks.append(original_name)
        except:
            pass

    # 第二階段：智慧型分段 AI 全中文深度解構
    ai_reports_dict = {}
    if success_stocks:
        try:
            ai_input_pool = {k: {
                "name": v["display_name"], "price": v["price"], "high": v["high"], "low": v["low"]
            } for k, v in market_data_batch.items()}
            
            prompt1 = f"你是一位擁有20年經驗的華爾街資深買方股票分析師。請針對數據池中的每一家公司進行前段投資解構，包含：1.執行摘要, 2.投資論點, 3.財務健康檢查, 4.估值評估。請完全使用「繁體中文」撰寫，內容要精煉專業。數據池：{json.dumps(ai_input_pool, ensure_ascii=False)}"
            response1 = client.models.generate_content(
                model='gemini-2.5-flash', contents=prompt1,
                config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=BatchPart1Schema, temperature=0.2),
            )
            raw_p1 = json.loads(response1.text).get("reports", [])
            
            time.sleep(3.5) # 物理防刷冷卻
            
            prompt2 = f"你是一位華爾街資深買方分析師。請根據上半部報告，繼續完成下半部深度點評，包含：5.競爭護城河與同業比較, 6.潛在風險提示, 7.綜合投資評級結論與行動建議。請完全使用「繁體中文」撰寫。上半部數據參考：{response1.text}"
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

    # 第三階段：整合與合規檢查
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
            final_output[t] = {"state": "FAILED", "error": f"基礎行情數據獲取失敗。可能受到跨國節點限制。"}
            
    return final_output

# 5. 主畫面手機優化直式面板渲染
with st.spinner("🕵️‍♂️ 華爾街資深分析師正在利用反阻擋架構下載數據，請稍候..."):
    results = fetch_all_and_analyze_batch(raw_ticker_list)

for t in raw_ticker_list:
    res = results.get(t, {"state": "FAILED", "error": "未知錯誤"})
    
    with st.container():
        if res["state"] in ["REPORT_COMPLETE", "MARKET_DATA_ONLY"]:
            p = res['price']
            price_str = f"${p:.2f}" if isinstance(p, (int, float)) else f"{p}"
            v = res['volume']
            vol_str = f"{v:,}" if isinstance(v, (int, float)) else f"{v}"
            
            st.markdown(f"## 🏢 {res['display_name']}")
            st.markdown(f"**即時現價：** `{price_str}` | **今日最高/最低：** `{res['high']:.2f}` / `{res['low']:.2f}` | **今日成交量：** `{vol_str}`")
            
            try:
                chart_df = pd.read_json(res["history_df"], orient='split')
                chart_df.columns = ['收盤價 (Close)', '20日均線 (MA20)', '布林上軌 (Upper Band)', '布林下軌 (Lower Band)']
                st.line_chart(chart_df, height=220) 
            except Exception as chart_err:
                st.caption(f"技術圖表渲染異常: {chart_err}")

            if res["state"] == "REPORT_COMPLETE":
                report_data = res["report"]
                rating_str = report_data.get("final_verdict_rating", "Not Rated")
                if "買" in rating_str or "Buy" in rating_str:
                    st.success(f"🎯 **機構綜合投資結論 (Final Verdict Rating)：{rating_str}**")
                elif "賣" in rating_str or "Sell" in rating_str:
                    st.error(f"🎯 **機構綜合投資結論 (Final Verdict Rating)：{rating_str}**")
                else:
                    st.warning(f"🎯 **機構綜合投資結論 (Final Verdict Rating)：{rating_str}**")
                    
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
                st.warning(f"⚠️ **無法給予 conclusions**：{res['error']}。")
        else:
            st.error(f"❌ 股票標的 **{t}** 基礎行情載入失敗。")
            st.caption(f"原因提示：{res.get('error')}")
            
        st.markdown("<br><hr style='margin:15px 0px; border-top: 2px dashed opacity:0.3;'>", unsafe_allow_html=True)
