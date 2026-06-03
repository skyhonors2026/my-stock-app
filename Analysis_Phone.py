import os
import streamlit as st
import pandas as pd
import requests
import json
from google import genai
from google.genai import types

# 1. 🚀 金鑰隱式注入機制
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

# 初始化 Session 記憶體，確保點擊其他按鈕時，已經生出來的報告不會消失
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
1. **行情秒級載入**：開啟網頁，全標的即時現價與布林通道線圖瞬間完成繪製。
2. **手動一鍵解構**：點擊個股下方的「解構基本面報告」，AI 現場即時生成，100% 完整吐出 7 大面向。
3. **無痛避開 429**：不採背景全自動併發，徹底告別空報告與流量限制！
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

# 智慧型機構級單股深度分析引擎
def analyze_stock_markdown(ticker_name, data_dict):
    try:
        prompt = f"""
        你是一位擁有20年經驗的華爾街資深買方股票分析師。请針對目標公司 {ticker_name} 的即時數據進行全面、深度且客觀的綜合投資分析報告。
        當前標的最新市況：{json.dumps(data_dict)}
        
        請嚴格遵循以下 7 大範疇框架，完全使用「繁體中文」輸出，無須提供任何英文翻譯，內容要精煉、充滿洞察。
        
        【報告格式規範】：
        ### 🔍 1. 執行摘要
        (核心業務模式與獲利引擎)
        
        ### ⚡ 2. 投資論點
        (看好或看空的3大專業理由)
        
        ### 🩺 3. 財務健康檢查
        (分析營收、利潤率與現金流狀況)
        
        ### ⚖️ 4. 估值評估
        (評估當前股價是否合理)
        
        ### 🛡️ 5. 競爭護城河與同業比較
        (分析競爭優勢與對手差異)
        
        ### 🚨 6. 潛在風險提示
        (指出公司特有的前3大潛在風險)
        
        ### 📢 7. 總結與最終行動建議
        【機構綜合投資結論】：[此處必須明確包含 '買入 (Buy)', '持有 (Hold)', 或 '賣出 (Sell)' 之一]
        核心操作邏輯支撐...
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=1200
            ),
        )
        
        if response and response.text:
            return {"success": True, "text": str(response.text).strip()}
        return {"success": False, "error": "AI 回傳了空內容"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# 4. 核心數據調度快取引擎
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

# 抓取並秒級繪製基礎行情與技術圖表
market_data = fetch_all_market_data(ticker_list)

# 5. 🎨 靜態與動態卡片混合渲染核心
for t in ticker_list:
    if t in market_data:
        data = market_data[t]
        p = data['price']
        price_str = f"${p:.2f}" if isinstance(p, (int, float)) else f"{p}"
        v = data['volume']
        vol_str = f"{v:,}" if isinstance(v, (int, float)) else f"{v}"
        
        # 1. 繪製基本市況
        st.markdown(f"## 🏢 {data['display_name']}")
        st.markdown(f"**即時現價：** `{price_str}` | **今日最高/最低：** `{data['high']:.2f}` / `{data['low']:.2f}` | **今日成交量：** `{vol_str}`")
        
        # 2. 繪製布林通道圖表
        try:
            chart_df = data["chart_df"].copy()
            chart_df.columns = ['收盤價 (Close)', '20日均線 (MA20)', '布林上軌 (Upper Band)', '布林下軌 (Lower Band)']
            st.line_chart(chart_df, height=220) 
        except:
            st.caption("技術圖表渲染中...")

        # 3. 💡 開箱型按鈕與記憶體渲染邏輯
        # 如果這檔股票之前已經點擊並生成過報告，直接顯示它
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
            # 如果還沒生成報告，顯示一個漂亮的開箱按鈕
            if st.button(f"🔍 點擊解構 {t} 基本面報告", key=f"btn_{t}"):
                with st.spinner(f"🕵️‍♂️ 華爾街分析師正在現場解構 {t} 數據..."):
                    ai_res = analyze_stock_markdown(t, {"name": data["display_name"], "price": data["price"]})
                    st.session_state.ai_reports_storage[t] = ai_res
                st.rerun() # 僅在點擊時重新整理一次，確保剛生成的報告立刻就地長出來
                
        st.markdown("<br><hr style='margin:15px 0px; border-top: 2px dashed opacity:0.3;'>", unsafe_allow_html=True)
    else:
        st.error(f"❌ 股票標的 **{t}** 基礎行情載入失敗。")
