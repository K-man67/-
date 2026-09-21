from datetime import date
import requests
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="權證風控雷達 V2.3", page_icon="🎯", layout="centered")

st.markdown("""
<style>
.stButton>button {width:100%; border-radius:8px; min-height:3em; background:#0d6efd; color:#fff; font-weight:bold; font-size:16px;}
.w-card {background:#fff; border:2px solid #cbd5e1; border-radius:12px; padding:16px; margin-bottom:15px; box-shadow:0 4px 10px rgba(0,0,0,.05);}
.tag {background:#be123c; color:#fff; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;}
</style>
""", unsafe_allow_html=True)

st.title("🎯 權證及格雷達 V2.3 (全天候穩定版)")
st.info("💡 證交所 API 欄位已自動相容，確保 2344 等標的能順利抓取！")

REPUTABLE_ISSUERS = ["元大", "凱基", "國泰", "富邦", "統一", "台新"]

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_basic():
    try:
        r = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap37_L", timeout=10).json()
        # 修正證交所 API 欄位名稱不固定的地雷
        return pd.DataFrame([{
            "code": d.get("權證代號", ""), 
            "name": d.get("權證名稱", ""), 
            "target": d.get("標的證券代號", d.get("標的代號", "")), 
            "target_name": d.get("標的證券名稱", d.get("標的名稱", "")),
            "type": "Put" if "售" in str(d.get("權證型態", d.get("權證類型", ""))) else "Call",
            "issuer": d.get("發行人", d.get("發行機構名稱", "")), 
            "strike": float(d.get("最新履約價格", d.get("履約價", 0))),
            "exp": d.get("到期日", ""),
            "out_ratio": float(d.get("最新權證數量", 0)) / float(d.get("發行時權證數量", 1)) * 100
        } for d in r if d.get("權證代號")])
    except: return pd.DataFrame()

def get_mis(codes):
    try:
        ex = "|".join(f"tse_{c}.tw" for c in codes)
        r = requests.get("https://mis.twse.com.tw/stock/api/getStockInfo.jsp", params={"ex_ch": ex}, timeout=5).json()
        return {d["c"]: {"last": float(d.get("z", 0) or 0), "bid": float(str(d.get("b","0_")).split("_")[0] or 0), "ask": float(str(d.get("a","0_")).split("_")[0] or 0)} for d in r.get("msgArray", [])}
    except: return {}

col1, col2 = st.columns([2, 1])
with col1: query = st.text_input("股票代碼/名稱", value="2344", placeholder="例: 2344 或 華邦電")
with col2: manual_spot = st.number_input("盤後參考現價", value=155.0, step=1.0)

t_type = "Put" if st.radio("方向", ["認售 (Put)", "認購 (Call)"], horizontal=True).startswith("認售") else "Call"
c1, c2 = st.columns(2)
with c1: min_days = st.slider("最少剩餘天數", 30, 150, 60)
with c2: max_spread = st.slider("盤中最大價差 %", 0.5, 5.0, 1.5, 0.5)

if st.button("🚀 開始全天候篩選"):
    q = query.strip().upper()
    with st.spinner("抓取與風控運算中..."):
        df = fetch_basic()
        if df.empty: st.error("證交所基本資料庫連線失敗，請稍後再試"); st.stop()
        
        mask = (df["target"].eq(q) | df["target_name"].str.contains(q, na=False)) & df["type"].eq(t_type)
        data = df[mask].copy()
        if data.empty: st.warning(f"查無標的【{query}】的上市 {t_type} 權證 (可能皆已下市或輸入錯誤)"); st.stop()
        
        today = date.today()
        data["days"] = data["exp"].apply(lambda x: (date(int(x[:3])+1911, int(x[3:5]), int(x[5:7])) - today).days if len(str(x))==7 else 0)
        data = data[data["days"] >= min_days] 
        
        targets = data["target"].unique().tolist()
        quotes = get_mis(targets + data["code"].tolist()[:25])
        
        is_live = bool(quotes) 
        spot = quotes.get(targets[0], {}).get("last", manual_spot) if targets else manual_spot
        if spot <= 0: spot = manual_spot
        
        res = []
        for _, r in data.iterrows():
            c, K = r["code"], r["strike"]
            m = ((K - spot)/spot*100) if r["type"]=="Put" else ((spot - K)/spot*100)
            
            bid = quotes.get(c, {}).get("bid", 0)
            ask = quotes.get(c, {}).get("ask", 0)
            spread = (ask - bid)/bid*100 if ask > bid > 0 else 0
            
            pass_hard = (r["issuer"] in REPUTABLE_ISSUERS) and (-5 <= m <= 10) and (r["out_ratio"] < 80)
            if is_live and bid > 0: pass_hard = pass_hard and (spread <= max_spread)
            
            if pass_hard:
                res.append({"code": c, "name": r["name"], "issuer": r["issuer"], "K": K, "days": r["days"], "m": m, "out": r["out_ratio"], "bid": bid, "ask": ask, "spread": spread, "abs_m": abs(m)})
                
        if not res:
            st.error(f"⚠️ 標的 {query} 現存權證皆未通過硬性門檻（發行商非白名單 / 深度價外 / 流通比過高 / 價差過大）。")
            st.stop()
            
        res_df = pd.DataFrame(res).sort_values("abs_m") 
        st.success(f"✅ [{'盤中即時模式' if is_live else '盤後靜態模式'}] 共篩選出 {len(res_df)} 檔合格權證 (現價基準: {spot})")
        
        for idx, r in enumerate(res_df.head(10).to_dict('records'), 1):
            badge = "👑 最佳首選" if idx == 1 else f"優選 #{idx}"
            live_info = f"<b>買/賣:</b> {r['bid']} / {r['ask']} (價差 {r['spread']:.2f}%)" if is_live and r['bid']>0 else "<b style='color:#ca8a04;'>狀態:</b> 盤後無報價 (系統已確認基本面及格，請於開盤確認委買賣單量)"
            
            st.markdown(f"""
            <div class="w-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="font-size:17px; font-weight:800; color:#0f172a;">{r['name']} ({r['code']})</div>
                    <span class="tag">{badge}</span>
                </div>
                <div style="font-size:13px; color:#475569; margin: 6px 0 10px 0;">發行商: <b>{r['issuer']}</b> | 履約價: <b>{r['K']}</b> | 流通比: <b>{r['out']:.1f}%</b></div>
                <hr style="border:0; border-top:1px solid #e2e8f0; margin: 8px 0;">
                <div style="font-size:14px; color:#1e293b; margin-bottom: 6px;"><b>價內外:</b> <span style="color:{'#dc2626' if r['m']>0 else '#16a34a'}; font-weight:bold;">{r['m']:+.1f}%</span> 　<b>剩餘天數:</b> {r['days']} 天</div>
                <div style="font-size:13px; color:#334155;">{live_info}</div>
            </div>
            """, unsafe_allow_html=True)
