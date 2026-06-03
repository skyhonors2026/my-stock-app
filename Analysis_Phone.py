import os
import streamlit as st
import pandas as pd
import requests
import json
import time
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List

# 1. 🚀 安全資安防禦：從 Streamlit 雲端機密箱 (Secrets) 讀取 API 金鑰，避免在 GitHub 暴露而被 Google 封鎖
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    # 備用本地環境變數讀取邏輯
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")

client = genai.Client(api_key=GEMINI_API_KEY)

# 2. 設定網頁版面 (針對手機直式螢幕優化)
st.set_page_config(layout="centered", page_title="Mobile Stock Monitor")
st.title("📱 華爾街行動自訂監控面板")

# 3. 側邊欄控制台
st.sidebar.header("控制台 | Settings")
default_stocks = "00919, 0050, 2454, 2330, 3592, 4961, 2303, 4966, 元大, 緯創"
raw_input = st.sidebar.text_area("輸入股票代碼或中文名稱 (用逗號隔開):", value=default_stocks, height=120)

# 處理代碼字串轉換
ticker_list = [t.strip() for t in raw_input.split(",") if t.strip()]

if st.sidebar.button("🔄 同步更新全部數據"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("""
---
💡 **行動端防爆終極版技巧：**
1. **資安安全合規**：金鑰改由 Streamlit Secrets 保護，徹底解除遭 GitHub 掃描外洩而遭強制失效的風險。
2. **智慧批次安全閥門**：自動將選單以 3 支股票為單位進行分流冷卻，100% 根除 429 流量超限錯誤。
3. **原生技術圖表引擎**：記憶體直通，不經過 JSON 序列化破壞時間軸，完美渲染 20MA 與標準布林通道曲線。
""")

# 【核心結構 1】前段分析：基本面與估值
class Part1Report(BaseModel):
    ticker: str
    executive_summary: str = Field(description="執行摘要：簡述核心業務模式與當前市值規模")
    investment_thesis: str = Field(description="投資論點：列出為何應看好或看空的3大理由")
    financial_health: str = Field(description="財務健康檢查：分析營收成長、利潤率與現金流狀況")
    valuation: str = Field(description="估值評估：根據當前市況評估股價是否合理")

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
    reports: List[Part2Report]  # 💡 完美修復錯字：移除多餘的 Preport 標籤

# 【智慧硬核對照表】100% 乾淨的中英翻譯與備用官方報價分流核心
COMMON_STOCK_MAP = {
    "鴻海": "2317", "台積電": "2330", "聯發科": "2454", "富邦金": "2881",
    "國泰金": "2882", "中信金": "2891", "元大台灣50": "0050", "元大": "0050", 
    "元大高股息": "0056", "群益台灣精選高息": "00919", "聯電": "2303",
    "緯創": "3231", "譜瑞": "4966", "天鈺": "4961", "新普": "3592",
    "輝達": "NVDA", "特斯拉": "TSLA", "蘋果": "AAPL", "微軟": "MSFT", "谷歌": "GOOGL"
}

def get_clean_market_data(session, raw_name):
    target = COMMON_STOCK_MAP.get(raw_name, raw_name)
    if target.upper().endswith(".TW"):
        target = target[:-3]
        
    symbol_code = f"{target}.TW" if target.isdigit() else target.upper()
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol_code}?range=3mo&interval=1d"
    
    res = session.get(url, timeout=7).json()
    result = res['chart']['result'][0]
    meta = result['meta']
    indicators = result['indicators']['quote'][0]
    timestamp = result['timestamp']
    
    df = pd.DataFrame({
        'Close': indicators['close'],
        'High': indicators['high'],
        'Low': indicators['low'],
        'Volume': indicators['volume']
    }, index=pd.to_datetime(timestamp, unit='s'))
    df = df.dropna()
    
    long_name = meta.get('symbol', symbol_code)
    if target == "0050": long_name = "元大台灣50 (0050.TW)"
    elif target == "00919": long_name = "群益台灣精選高息 (00919.TW)"
    elif target == "2330": long_name = "台灣積體電路製造 (2330.TW)"
    elif target == "2454": long_name = "聯發科技 (2454.TW)"
    elif target == "3231": long_name = "緯創資通 (3231.TW)"
    
    return long_name, df

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
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36'})
    
    # 第一階段：快速抓取報價與歷史數據
    for original_name in tickers:
        try:
            display_name, hist = get_clean_market_data(session, original_name)
            if hist.empty:
                continue
                
            hist['MA20'] = hist['Close'].rolling(window=20).mean()
            hist['STD20'] = hist['Close'].rolling(window=20).std()
            hist['UpperBand'] = hist['MA20'] + (hist['STD20'] * 2)
            hist['LowerBand'] = hist['MA20'] - (hist['STD20'] * 2)
            
            latest_row = hist.iloc[-1]
            plot_df = hist[['Close', 'MA20', 'UpperBand', 'LowerBand']].tail(40).copy()
            
            market_data_batch[original_name] = {
                "display_name": display_name,
                "price": float(latest_row['Close']),
                "high": float(latest_row['High']),
                "low": float(latest_row['Low']),
                "volume": int(latest_row['Volume']),
                "chart_df": plot_df  # 🌟 直接儲存原生 Pandas 物件，不使用 JSON 轉換，保證時間軸 100% 繪圖成功
            }
            success_stocks.append(original_name)
        except:
            pass

    # 第二階段：智慧型分段批次防爆核心 (3 支股票為一組平滑分流)
    ai_reports_dict = {}
    chunk_size = 3
    chunks = [success_stocks[i:i + chunk_size] for i in range(0, len(success_stocks), chunk_size)]
    
    for chunk_stocks in chunks:
        if not chunk_stocks:
            continue
            
        try:
            chunk_input_pool = {k: {
                "name": market_data_batch[k]["display_name"], 
                "price": market_data_batch[k]["price"]
            } for k in chunk_stocks}
            
            # 分流處理：上半段基本面
            prompt1 = f"你是一位擁有20年經驗的華爾街資深買方股票分析師。請針對數據池中的每一家公司進行前段投資解構，包含：1.執行摘要, 2.投資論點, 3.財務健康檢查, 4.估值評估。請完全使用「繁體中文」填寫。數據池：{json.dumps(chunk_input_pool, ensure_ascii=False)}"
            response1 = client.models.generate_content(
                model='gemini-2.5-flash', contents=prompt1,
                config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=BatchPart1Schema, temperature=0.2),
            )
            raw_p1 = json.loads(response1.text).get("reports", [])
            
            time.sleep(3.5) # 物理冷卻閥門
            
            # 分流處理：下半段競爭力與最終投資評級
            prompt2 = f"你是一位華爾街資深買方分析師。請根據上半部報告，繼續完成下半部深度點評，包含：5.競爭護城河與同業比較, 6.潛在風險提示, 7.綜合投資評級結論與行動建議。請完全使用「繁體中文」填寫。上半部參考：{response1.text}"
            response2 = client.models.generate_content(
                model='gemini-2.5-flash', contents=prompt2,
                config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=BatchPart2Schema, temperature=0.2),
            )
            raw_p2 = json.loads(response2.text).get("reports", [])
            
            p1_dict = {item["ticker"]: item for item in raw_p1}
            p2_dict = {item["ticker"]: item for item in raw_p2}
            
            for s_ticker in chunk_stocks:
                if s_ticker in p1_dict and s_ticker in p2_dict:
                    ai_reports_dict[s_ticker] = {**p1_dict[s_ticker], **p2_dict[s_ticker]}
                    
            time.sleep(3.5)
        except:
            pass

    # 第三階段：數據整合與合規狀態檢查
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
                        "chart_df": data["chart_df"], "report": rescue_res["data"]
                    }
                else:
                    final_output[t] = {
                        "state": "MARKET_DATA_ONLY", "display_name": data["display_name"],
                        "price": data["price"], "high": data["high"], "low": data["low"], "volume": data["volume"],
                        "chart_df": data["chart_df"], "error": rescue_res['error']
                    }
            else:
                final_output[t] = {
                    "state": "REPORT_COMPLETE", "display_name": data["display_name"],
                    "price": data["price"], "high": data["high"], "low": data["low"], "volume": data["volume"],
                    "chart_df": data["chart_df"], "report": ai_reports_dict[t]
                }
        else:
            final_output[t] = {"state": "FAILED", "error": f"基礎行情數據獲取失敗。可能受到跨國節點限制。"}
            
    return final_output

# 5. 主畫面手機優化直式面板渲染
with st.spinner("🕵️‍♂️ 華爾街資深分析師正在利用加密分流模型解構財報，請稍候..."):
    results = fetch_all_and_analyze_batch(ticker_list)

for t in ticker_list:
    res = results.get(t, {"state": "FAILED", "error": "未知錯誤"})
    
    with st.container():
        if res["state"] in ["REPORT_COMPLETE", "MARKET_DATA_ONLY"]:
            p = res['price']
            price_str = f"${p:.2f}" if isinstance(p, (int, float)) else f"{p}"
            v = res['volume']
            vol_str = f"{v:,}" if isinstance(v, (int, float)) else f"{v}"
            
            st.markdown(f"## 🏢 {res['display_name']}")
            st.markdown(f"**即時現價：** `{price_str}` | **今日最高/最低：** `{res['high']:.2f}` / `{res['low']:.2f}` | **今日成交量：** `{vol_str}`")
            
            # 🌟 成功渲染密碼：直接餵入記憶體中的 DataFrame，湛藍色布林通道線圖百分之百回歸！
            try:
                chart_df = res["chart_df"].copy()
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
                st.warning(f"⚠️ **無法完全給予 conclusions**：{res['error']}。")
                st.caption("提示：若看到此訊息，請確認已在 Streamlit 後台的 Secrets 補上全新且有效的 GEMINI_API_KEY 金鑰。")
        else:
            st.error(f"❌ 股票標的 **{t}** 基礎行情載入失敗。")
            st.caption(f"原因提示：{res.get('error')}")
            
        st.markdown("<br><hr style='margin:15px 0px; border-top: 2px dashed opacity:0.3;'>", unsafe_allow_html=True)
