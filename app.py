from datetime import date
import requests
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="權證智能評級雷達", page_icon="🎯", layout="centered")

# 極簡高對比 CSS
st.markdown("""
<style>
.stButton>button {width:100%; border-radius:8px; min-height:3em; background:#0d6efd; color:#fff; font-weight:bold; font-size:16px;}
.w-card {background:#fff; border:2px solid #cbd5e1; border-radius:12px; padding:16px; margin-bottom:15px; box-shadow:0 4px 10px rgba(0,0,0,.05);}
.tag {background:#be123c; color:#fff; padding:3px 8px; border-radius:4px; font-size:12px; font-weight:bold;}
.diag-box {background:#f8fafc; border-left:4px solid #3b82f6; padding:12px; margin-top:12px; border-radius:6px; font-size:13px; line-height:1.7; color:#334155;}
</style>
""", unsafe_allow_html=True)

st.title("🎯 權證智能評級雷達 V2.5")
st.info("💡 API 欄位地雷已全面修復，台積電等上市櫃權證皆可精準掃描。")

# 白名單
REPUTABLE_ISSUERS = ["元大", "凱基", "國泰", "富邦", "統一", "台新", "玉山"]

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_basic():
    try:
        r1 = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap37_L", timeout=10).json()
        r2 = requests.get("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap37_O", timeout=10).json()
        raw = (r1 if isinstance(r1, list) else []) + (r2 if isinstance(r2, list) else [])
        
        res = []
        for d in raw:
            # 暴力相容上市與上櫃的欄位名稱差異
            code = str(d.get("證券代號", d.get("權證代號", ""))).strip()
            if not code: continue
            
            name = str(d.get("證券名稱", d.get("權證名稱", ""))).strip()
            target = str(d.get("標的證券代號", d.get("標的代號", ""))).strip()
            target_name = str(d.get("標的證券名稱", d.get("標的名稱", ""))).strip()
            
            # 雙重防呆：從欄位判斷，若無則從名稱抓取「售」字
            w_type = "Put" if "售" in str(d.get("權證型態", d.get("型態", ""))) or "售" in name else "Call"
            
            issuer = str(d.get("發行機構名稱", d.get("發行人", ""))).strip()
            strike = float(d.get("最新履約價格", d.get("履約價", 0)) or 0)
            exp = str(d.get("到期日", ""))
            
            # 避免除以 0 的保護機制
            issue_qty = float(d.get("發行時權證數量", 1) or 1)
            latest_qty = float(d.get("最新權證數量", 0) or 0)
            out_ratio = (latest_qty / issue_qty) * 100 if issue_qty > 0 else 0
            
            res.append({
                "code": code, "name": name, "target": target, "target_name": target_name,
                "type": w_type, "issuer": issuer, "strike": strike, "exp": exp, "out_ratio": out_ratio
            })
        return pd.DataFrame(res)
    except: return pd.DataFrame()

def get_mis(codes):
    if not codes: return {}
    res = {}
    for i in range(0, len(codes), 50):
        ex = "|".join(f"tse_{c}.tw" for c in codes[i:i+50]) + "|" + "|".join(f"otc_{c}.tw" for c in codes[i:i+50])
        try:
            r = requests.get("https://mis.twse.com.tw/stock/api/getStockInfo.jsp", params={"ex_ch": ex}, timeout=5).json()
            for d in r.get("msgArray", []):
                z = d.get("z", "")
                if z == "-" or not z: z = d.get("y", "0") 
                b = str(d.get("b", "0_")).split("_")[0]
                a = str(d.get("a", "0_")).split("_")[0]
                res[d["c"]] = {"last": float(z) if z else 0, "bid": float(b) if b else 0, "ask": float(a) if a else 0}
        except: pass
    return res

query = st.text_input("股票代碼 / 名稱", value="2330", placeholder="例: 2330 或 台積電")
t_type = "Put" if st.radio("權證方向", ["認購 (Call)", "認售 (Put)"], horizontal=True).startswith("認售") else "Call"

if st.button("🚀 開始智能評級"):
    q = query.strip().upper()
    with st.spinner("抓取全市場資料與風控體檢中..."):
        df = fetch_basic()
        if df.empty: st.error("證交所基本資料庫連線失敗，請稍後再試"); st.stop()
        
        # 模糊比對標的名稱或代碼
        mask = (df["target"].eq(q) | df["target_name"].str.contains(q, na=False)) & df["type"].eq(t_type)
        data = df[mask].copy()
        
        if data.empty: 
            st.warning(f"💡 查無標的【{query}】的上市櫃 {t_type} 權證 (可能未發行或已全數下市)")
            st.stop()
            
        today = date.today()
        data["days"] = data["exp"].apply(lambda x: (date(int(x[:3])+1911, int(x[3:5]), int(x[5:7])) - today).days if len(str(x))==7 else 0)
        
        targets = data["target"].unique().tolist()
        quotes = get_mis(targets + data["code"].tolist())
        
        spot = quotes.get(targets[0], {}).get("last", 0) if targets else 0
        if spot <= 0: st.error("無法取得該標的之現價資訊，請確認是否為上市櫃股票"); st.stop()
        
        res = []
        for _, r in data.iterrows():
            c, K = r["code"], r["strike"]
            m = ((K - spot)/spot*100) if r["type"]=="Put" else ((spot - K)/spot*100)
            
            bid = quotes.get(c, {}).get("bid", 0)
            ask = quotes.get(c, {}).get("ask", 0)
            spread = (ask - bid)/bid*100 if ask > bid > 0 else 0
            
            c_issuer = r["issuer"] in REPUTABLE_ISSUERS
            c_days = r["days"] >= 60
            c_money = -5 <= m <= 10
            c_out = r["out_ratio"] < 80
            c_spread = bid > 0 and spread <= 2.5
            
            score = sum([c_issuer, c_days, c_money, c_out, c_spread])
            
            res.append({
                "code": c, "name": r["name"], "issuer": r["issuer"], "K": K, 
                "days": r["days"], "m": m, "out": r["out_ratio"], "bid": bid, "ask": ask, 
                "spread": spread, "abs_m": abs(m), "score": score,
                "c_issuer": c_issuer, "c_days": c_days, "c_money": c_money, "c_out": c_out, "c_spread": c_spread
            })
            
        res_df = pd.DataFrame(res).sort_values(by=["score", "abs_m"], ascending=[False, True])
        st.success(f"✅ 成功掃描 {len(res_df)} 檔權證 (現價基準: {spot})")
        
        for idx, r in enumerate(res_df.head(15).to_dict('records'), 1):
            if r['score'] == 5: star, grade = "★★★★★", "S級 (完美標的)"
            elif r['score'] == 4: star, grade = "★★★★☆", "A級 (優良標的)"
            elif r['score'] == 3: star, grade = "★★★☆☆", "B級 (尚可接受)"
            else: star, grade = "★★☆☆☆", "C級 (風險較高)"
            
            badge = f"🏆 第 {idx} 名" if idx <= 3 else f"排位 #{idx}"
            
            msg_issuer = f"✅ <b>發行券商：</b>{r['issuer']} (造市白名單)" if r['c_issuer'] else f"❌ <b>發行券商：</b>{r['issuer']} (非首選名單)"
            msg_days = f"✅ <b>剩餘天數：</b>{r['days']} 天 (安全，時間耗損低)" if r['c_days'] else f"❌ <b>剩餘天數：</b>{r['days']} 天 (低於60天，時間耗損極快)"
            msg_money = f"✅ <b>履約位置：</b>{r['m']:+.1f}% (處於價平甜蜜區)" if r['c_money'] else f"❌ <b>履約位置：</b>{r['m']:+.1f}% (偏離最佳區間)"
            msg_out = f"✅ <b>籌碼結構：</b>流通比 {r['out']:.1f}% (券商庫存充足)" if r['c_out'] else f"❌ <b>籌碼結構：</b>流通比 {r['out']:.1f}% (過高，易遭散戶溢價)"
            
            if r['bid'] > 0:
                msg_spread = f"✅ <b>流動性：</b>價差 {r['spread']:.1f}% (進出摩擦成本低)" if r['c_spread'] else f"❌ <b>流動性：</b>價差 {r['spread']:.1f}% (價差過大，吃單成本高)"
            else:
                msg_spread = "⏸️ <b>流動性：</b>盤後無報價 (請於盤中確認五檔委買賣)"

            st.markdown(f"""
            <div class="w-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="font-size:17px; font-weight:800; color:#0f172a;">{r['name']} ({r['code']})</div>
                    <span class="tag">{badge}</span>
                </div>
                <div style="font-size:14px; color:#1e293b; margin-top:8px;"><b>買/賣:</b> {r['bid']} / {r['ask']} 　<b>履約價:</b> {r['K']}</div>
                
                <div class="diag-box">
                    <div style="color:#0f172a; font-weight:bold; margin-bottom:4px; font-size:14px;">
                        綜合評級：{star} {grade}
                    </div>
                    {msg_issuer}<br>
                    {msg_days}<br>
                    {msg_money}<br>
                    {msg_out}<br>
                    {msg_spread}
                </div>
            </div>
            """, unsafe_allow_html=True)
