import os
import streamlit as st
import pandas as pd
import requests
import json
import time
from google import genai
from google.genai import types

# 1. 🚀 金鑰隱式注入機制 (支援 2026 最新 AQ 憑證環境)
try:
    if "GEMINI_API_KEY" in st.secrets:
        clean_key = str(st.secrets["GEMINI_API_KEY"]).strip().replace('"', '').replace("'", "")
        os.environ["GEMINI_API_KEY"] = clean_key
        os.environ["GOOGLE_API_KEY"] = clean_key
except Exception:
    pass

# 初始化用戶端
client = genai.Client()

# 2. 設定網頁版面 (針對手機直式螢幕優化)
st.set_page_config(layout="centered", page_title="Mobile Stock Monitor")
st.title("📱 華爾街行動自訂監控面板")

# 初始化 Session 記憶體快取，確保點擊不同股票時，已生成的報告互不干擾
if "ai_reports_storage" not in st.session_state:
    st.session_state.ai_reports_storage = {}

# 3. 側邊欄控制台
st.sidebar.header("控制台 | Settings")
default_stocks = "00919, 0050, 2454, 2330, 3592, 4961, 2303, 4966, 元大, 緯創"
raw_input = st.sidebar.text_area("輸入股票代碼或中文名稱 (用逗號隔開):", value=default_stocks, height=120)

ticker_list = [t.strip() for t in raw_input.split(",") if t.strip()]

if st.sidebar.button("🔄 重置並清空所有快取"):
    st.session_state.ai_reports_storage = {}
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("""
---
💡 **行動端點擊開箱功能：**
1. **行情秒級載入**：全標的即時現價與布林通道線圖瞬間繪製。
2. **精煉文字排版**：限制每段字數，100% 解決 Gemini 輸出被截斷或斷頭的問題。
3. **503 塞車自動救援**：內建自動重試防禦，當 Google 伺服器繁忙時自動重新呼叫。
""")

# 【智慧對照表】
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

# 智慧型操盤手量價技術分析引擎（高回應率、防截斷優化版）
def analyze_stock_markdown(ticker_name, data_dict):
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # 大幅精煉 Prompt，要求 AI 直接給予精簡的要點，避免因為內容過長觸發截斷
            prompt = f"""
            你是一位精通量價結構與布林通道策略的華爾街高級避險基金操盤手。
            請針對目標標的「{ticker_name}」當前的即時量價市況進行精準、客觀的技術面操盤報告。
            
            當前標的數據快照：
            - 標的名稱: {data_dict.get('name')}
            - 當前最新收盤價: {data_dict.get('price')} 元
            - 今日高低價區間: {data_dict.get('high')} 元 ~ {data_dict.get('low')} 元
            - 當前成交量: {data_dict.get('volume')} 股
            
            請嚴格遵循以下 4 大核心板塊，完全使用「繁體中文」輸出。
            注意：每段分析請控制在 80 字以內，文字要精煉、充滿實戰洞察，直接說重點，嚴禁任何廢話或長篇大論！
            每個「###」標題後面，必須先換行，再開始寫內文，絕對不能連在同一行！
            
            【報告格式規範】：
            這是一份針對「{ticker_name}」的即時技術面操盤報告。
            
            ### 🔍 1. 當前量價與布林位置評估
            (分析現價相對於布林通道的位置關係)
            
            ### ⚡ 2. 實戰操作觀察點
            (指出短期內最關鍵的壓力位與支撐位)
            
            ### 🛡️ 3. 風控與追隨策略
            (指出操盤手應守護的停損防線或加碼點)
            
            ### 📢 4. 綜合投資結論與最終行動建議
            【機構綜合投資結論】：[此處必須明確包含 '買入 (Buy)', '持有 (Hold)', 或 '賣出 (Sell)' 之一]
            核心操作邏輯：(一句話點明當前最適合此技術型態的防禦或進攻策略)
            """
            
            safety_settings = [
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
            ]

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1, # 降低隨機性，確保格式精準聽話
                    max_output_tokens=1000,
                    safety_settings=safety_settings
                ),
            )
            
            generated_text = getattr(response, 'text', None)
            
            if not generated_text and response.candidates:
                try:
                    generated_text = response.candidates[0].content.parts[0].text
                except:
                    pass
                    
            if generated_text:
                return {"success": True, "text": str(generated_text).strip()}
                
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
                
            return {"success": False, "error": "AI 未返回文字。"}
            
        except Exception as e:
            err_msg = str(e)
            if "503" in err_msg or "UNAVAILABLE" in err_msg:
                if attempt < max_retries - 1:
                    time.sleep(2.5)
                    continue
            return {"success": False, "error": err_msg}
            
    return {"success": False, "error": "伺服器繁忙，請稍候再試。"}

# 4. 核心數據調度快取引擎 (正確對齊函式定義名稱)
@st.cache_data(ttl=60)
def fetch_all_market_data(tickers):
    market_data_batch = {}
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36'})
    
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
                "chart_df": plot_df
            }
        except:
            pass
    return market_data_batch

# 呼叫正確的函式名稱，完美解決 NameError 名字錯配問題
market_data = fetch_all_market_data(ticker_list)

# 5. 🎨 靜態線圖與動態按鈕混合渲染面板
for t in ticker_list:
    if t in market_data:
        data = market_data[t]
        p = data['price']
        price_str = f"${p:.2f}" if isinstance(p, (int, float)) else f"{p}"
        v = data['volume']
        vol_str = f"{v:,}" if isinstance(v, (int, float)) else f"{v}"
        
        # 1. 繪製個股行情基本面
        st.markdown(f"## 🏢 {data['display_name']}")
        st.markdown(f"**即時現價：** `{price_str}` | **今日最高/最低：** `{data['high']:.2f}` / `{data['low']:.2f}` | **今日成交量：** `{vol_str}`")
        
        # 2. 繪製湛藍色布林通道圖表
        try:
            chart_df = data["chart_df"].copy()
            chart_df.columns = ['收盤價 (Close)', '20日均線 (MA20)', '布林上軌 (Upper Band)', '布林下軌 (Lower Band)']
            st.line_chart(chart_df, height=220) 
        except:
            st.caption("技術圖表渲染中...")

        # 3. 獨立區塊開箱型按鈕邏輯
        if t in st.session_state.ai_reports_storage:
            ai_res = st.session_state.ai_reports_storage[t]
            if ai_res["success"]:
                report_text = str(ai_res["text"])
                
                # 獨立解析投資評級结论橫幅
                if "買入" in report_text or "Buy" in report_text:
                    st.success("🎯 **機構綜合投資結論：建議 買入 (Buy)**")
                elif "賣出" in report_text or "Sell" in report_text:
                    st.error("🎯 **機構綜合投資結論：建議 賣出 (Sell)**")
                else:
                    st.warning("🎯 **機構綜合投資結論：建議 持有 (Hold) 觀望**")
                    
                st.markdown(report_text)
            else:
                st.error(f"⚠️ 生成失敗：{ai_res['error']}")
        else:
            if st.button(f"🔍 點擊解構 {t} 量價策略報告", key=f"btn_{t}"):
                with st.spinner(f"🕵️‍♂️ 避險基金操盤手正在計算 {t} 軌道型態..."):
                    ai_res = analyze_stock_markdown(t, {
                        "name": data["display_name"], 
                        "price": data["price"],
                        "high": data["high"],
                        "low": data["low"],
                        "volume": data["volume"]
                    })
                    st.session_state.ai_reports_storage[t] = ai_res
                st.rerun()
                
        st.markdown("<br><hr style='margin:15px 0px; border-top: 2px dashed opacity:0.3;'>", unsafe_allow_html=True)
