import os
import streamlit as st
import pandas as pd
import requests
import json
import time
from google import genai
from google.genai import types

# 1. 🚀 金鑰隱式注入機制 (同時注入雙軌變數以支援新型 AQ 憑證)
try:
    if "GEMINI_API_KEY" in st.secrets:
        clean_key = str(st.secrets["GEMINI_API_KEY"]).strip().replace('"', '').replace("'", "")
        os.environ["GEMINI_API_KEY"] = clean_key
        os.environ["GOOGLE_API_KEY"] = clean_key
except Exception:
    pass

# 初始化 Gemini 用戶端
client = genai.Client()

# 2. 設定網頁版面 (針對手機直式螢幕優化)
st.set_page_config(layout="centered", page_title="Mobile Stock Monitor")
st.title("📱 華爾街行動自訂監控面板")

# 初始化 Session 記憶體快取
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

# 4. 數據獲取引擎
@st.cache_data(ttl=60)
def fetch_all_market_data(tickers):
    market_data_batch = {}
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36'})
    
    stock_map = {
        "鴻海": "2317", "台積電": "2330", "聯發科": "2454", "富邦金": "2881",
        "國泰金": "2882", "中信金": "2891", "元大台灣50": "0050", "元大": "0050", 
        "元大高股息": "0056", "群益台灣精選高息": "00919", "聯電": "2303",
        "緯創": "3231", "譜瑞": "4966", "天鈺": "4961", "新普": "3592",
        "輝達": "NVDA", "特斯拉": "TSLA", "蘋果": "AAPL", "微軟": "MSFT", "谷歌": "GOOGL"
    }
    
    for original_name in tickers:
        try:
            target = stock_map.get(original_name, original_name)
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
            
            hist = df.copy()
            hist['MA20'] = hist['Close'].rolling(window=20).mean()
            hist['STD20'] = hist['Close'].rolling(window=20).std()
            hist['UpperBand'] = hist['MA20'] + (hist['STD20'] * 2)
            hist['LowerBand'] = hist['MA20'] - (hist['STD20'] * 2)
            
            latest_row = hist.iloc[-1]
            plot_df = hist[['Close', 'MA20', 'UpperBand', 'LowerBand']].tail(40).copy()
            
            market_data_batch[original_name] = {
                "display_name": long_name,
                "price": float(latest_row['Close']),
                "high": float(latest_row['High']),
                "low": float(latest_row['Low']),
                "volume": int(latest_row['Volume']),
                "chart_df": plot_df
            }
        except:
            pass
    return market_data_batch

# 極速量價分析引擎 (100% 杜絕截斷，高強迫性短句輸出)
def analyze_stock_markdown(ticker_name, data_dict):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 💡 終極修復：完全去掉任何可能引發過長背誦的引言，改為高強度指令，強制使用簡單短句
            prompt = f"""
            你是一位專業操盤手。請針對「{ticker_name}」進行極簡技術面點評。
            最新數據：價格 {data_dict.get('price')} 元，今日區間 {data_dict.get('high')}~{data_dict.get('low')}，成交量 {data_dict.get('volume')} 股。
            
            請強制且必須使用「純繁體中文」輸出以下四行，每行請直接寫結論，嚴禁超過40個字：
            
            - 軌道型態：(直接填寫股價相對於布林通道的位置)
            - 實戰觀察：(直接填寫短期關鍵壓力與支撐價位)
            - 風控防線：(直接填寫建議停損或守護的目標價)
            - 機構結論：[此處必須明確包含 '買入', '持有', 或 '賣出' 之一]
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
                    temperature=0.4,  # 微幅拉高，防止低溫截斷
                    max_output_tokens=600,
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
            return {"success": False, "error": "模型未返回內容。"}
        except Exception as e:
            err_msg = str(e)
            if "503" in err_msg or "UNAVAILABLE" in err_msg:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
            return {"success": False, "error": err_msg}
            
    return {"success": False, "error": "伺服器繁忙。"}

# 5. 🎨 畫面渲染核心
market_data = fetch_all_market_data(ticker_list)

for t in ticker_list:
    if t in market_data:
        data = market_data[t]
        p = data['price']
        price_str = f"${p:.2f}" if isinstance(p, (int, float)) else f"{p}"
        v = data['volume']
        vol_str = f"{v:,}" if isinstance(v, (int, float)) else f"{v}"
        
        st.markdown(f"## 🏢 {data['display_name']}")
        st.markdown(f"**即時現價：** `{price_str}` | **今日最高/最低：** `{data['high']:.2f}` / `{data['low']:.2f}` | **今日成交量：** `{vol_str}`")
        
        try:
            chart_df = data["chart_df"].copy()
            chart_df.columns = ['收盤價 (Close)', '20日均線 (MA20)', '布林上軌 (Upper Band)', '布林下軌 (Lower Band)']
            st.line_chart(chart_df, height=220) 
        except:
            st.caption("技術圖表渲染中...")

        # 報告快取與渲染邏輯
        if t in st.session_state.ai_reports_storage:
            ai_res = st.session_state.ai_reports_storage[t]
            if ai_res["success"]:
                report_text = str(ai_res["text"])
                
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
