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
3. **安全防鎖優化**：修復 SDK text 屬性解析錯誤，加入極寬安全防護閥，報告輸出 100% 穩定。
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
        
        # 設置最高級別的防過濾解鎖設定
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
                temperature=0.2,
                max_output_tokens=1200,
                safety_settings=safety_settings
            ),
        )
        
        # 🌟 安全檢查點：使用 getattr 避免 'object has no attribute text' 錯誤
        generated_text = getattr(response, 'text', None)
        
        # 如果 text 屬性不存在，嘗試從 candidates 結構中手動提取
        if not generated_text and response.candidates:
            try:
                generated_text = response.candidates[0].content.parts[0].text
            except:
                pass
                
        if generated_text:
            return {"success": True, "text": str(generated_text).strip()}
            
        # 如果依然
