from datetime import date, timedelta
import math, re
import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="權證風控雷達 V2.1", page_icon="🎯", layout="centered")

st.markdown("""
<style>
.stButton>button {width: 100%; border-radius: 9px; min-height: 3.1em; background: #0d6efd; color: #fff; font-weight: 800; font-size: 16px;}
.warrant-card {background: #fff; border: 2px solid #cbd5e1; border-radius: 14px; padding: 16px; margin: 0 0 16px 0; box-shadow: 0 4px 12px rgba(0,0,0,.06);}
.title {color: #0f172a; font-size: 18px; font-weight: 850; margin: 0;}
.sub, .small {color: #334155; font-size: 13px; margin: 5px 0 10px 0;}
.reason {background: #fefce8; border-left: 4px solid #ca8a04; padding: 12px; margin-top: 12px; border-radius: 6px; color: #713f12; font-size: 13px; line-height: 1.65;}
.badge {display: inline-block; color: white; padding: 4px 9px; border-radius: 5px; font-size: 11px; font-weight: 900;}
</style>
""", unsafe_allow_html=True)

st.warning("⚠️ 風控提示：盤中下單前仍須在券商 App 核對五檔委買賣單量是否正常掛出，嚴禁使用市價單追價。")
st.title("🎯 權證風控及格雷達 V2.1")

REPUTABLE_ISSUERS = ["元大", "凱基", "國泰", "富邦", "統一", "台新"]
TWSE_OPENAPI = "https://openapi.twse.com.tw/v1"
TWSE_MIS = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"

# 工具函式
def safe_float(x):
    try: return float(str(x).strip().replace(",", "").replace("%", ""))
    except: return np.nan

def get_warrant_tick(price):
    if not np.isfinite(price): return np.nan
    if price < 5: return 0.01
    if price < 10: return 0.05
    if price < 50: return 0.10
    return 0.50

# API 抓取
@st.cache_data(ttl=600, show_spinner=False)
def fetch_warrant_basic():
    r = requests.get(f"{TWSE_OPENAPI}/opendata/t187ap37_L", timeout=12).json()
    rows = []
    for d in r:
        try:
            code = d.get("權證代號", "")
            if not code: continue
            wtype = "Put" if "售" in d.get("權證型態", "") else "Call"
            rows.append({
                "code": code, "name": d.get("權證名稱", code), "type": wtype,
                "issuer": d.get("發行人", ""), "target": d.get("標的代號", ""),
                "target_name": d.get("標的名稱", ""), "strike": safe_float(d.get("履約價", np.nan)),
                "ratio": safe_float(d.get("行使比例", np.nan)), "expiration": d.get("到期日", ""),
                "outstanding_ratio": safe_float(d.get("最新權證數量", 0)) / safe_float(d.get("發行時權證數量", 1)) * 100
            })
        except: continue
    return pd.DataFrame(rows)

@st.cache_data(ttl=20, show_spinner=False)
def fetch_mis_quotes(codes):
    if not codes: return pd.DataFrame()
    ex = "|".join(f"tse_{c}.tw" for c in codes)
    try:
        r = requests.get(TWSE_MIS, params={"ex_ch": ex}, timeout=8).json()
        rows = []
        for d in r.get("msgArray", []):
            b = str(d.get("b", "")).split("_")[0]
            a = str(d.get("a", "")).split("_")[0]
            rows.append({"code": d.get("c"), "last": safe_float(d.get("z")), "bid": safe_float(b), "ask": safe_float(a)})
        return pd.DataFrame(rows)
    except: return pd.DataFrame()

# Black-Scholes 運算
def norm_cdf(x): return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
def bs_price(S, K, T, r, sigma, kind):
    if min(S, K, T, sigma) <= 0: return np.nan
    d1 = (math.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*math.sqrt(T))
    d2 = d1 - sigma*math.sqrt(T)
    if kind == "Call": return S*norm_cdf(d1) - K*math.exp(-r*T)*norm_cdf(d2)
    return K*math.exp(-r*T)*norm_cdf(-d2) - S*norm_cdf(-d1)

def bs_greeks(S, K, T, r, sigma, kind):
    if min(S, K, T, sigma) <= 0: return np.nan
    d1 = (math.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*math.sqrt(T))
    return norm_cdf(d1) if kind == "Call" else norm_cdf(d1) - 1

def implied_volatility(pm, S, K, T, r, ratio, kind):
    if min(pm, S, K, T, ratio) <= 0: return np.nan
    lo, hi, opt = 0.001, 4.0, pm/ratio
    for _ in range(50):
        mid = (lo + hi)/2
        p = bs_price(S, K, T, r, mid, kind)
        if not np.isfinite(p): return np.nan
        if p > opt: hi = mid
        else: lo = mid
    return (lo + hi)/2

# UI 介面
query = st.text_input("查詢標的代碼 / 權證名稱", value="2327", placeholder="例: 2327、國巨、2344")
target_type = "Put" if st.radio("方向", ["認售 (Put)", "認購 (Call)"], horizontal=True).startswith("認售") else "Call"
col1, col2 = st.columns(2)
with col1: min_days = st.slider("最少天數", 30, 150, 60)
with col2: max_spread = st.slider("最大價差 %", 0.5, 5.0, 2.0, 0.5)

if st.button("🚀 開始即時安全篩選"):
    q = query.strip().upper()
    with st.spinner("連接證交所獲取資料中..."):
        basic = fetch_warrant_basic()
        mask = (basic["target"].astype(str).str.upper().eq(q) | basic["name"].astype(str).str.upper().str.contains(q))
        data = basic.loc[mask & basic["type"].eq(target_type)].copy()
        
        if data.empty:
            st.warning("查無相關上市權證。")
            st.stop()
            
        targets = tuple(data["target"].dropna().unique())
        t_quotes = fetch_mis_quotes(targets)
        if not t_quotes.empty:
            data = data.merge(t_quotes[["code", "last"]].rename(columns={"code": "target", "last": "spot"}), on="target", how="left")
        else: data["spot"] = np.nan
        
        # 效能初篩
        data["days"] = pd.to_datetime(data["expiration"].apply(lambda x: str(int(x[:3])+1911)+x[3:] if pd.notnull(x) and len(str(x))==7 else np.nan), errors='coerce').apply(lambda d: (d.date() - date.today()).days if pd.notnull(d) else np.nan)
        data = data[data["days"] >= min_days - 10]
        
        # 抓報價
        quotes = fetch_mis_quotes(tuple(data["code"].tolist()[:25]))
        if not quotes.empty: data = data.merge(quotes, on="code", how="inner")
        else: st.error("非盤中或連線受限。"); st.stop()

        # 分析
        res = []
        for _, r in data.iterrows():
            spot, K, T = r.get("spot", np.nan), r.get("strike", np.nan), r.get("days", 0)/365.0
            bid, ask, ratio = r.get("bid", np.nan), r.get("ask", np.nan), r.get("ratio", 0)
            
            if not np.isfinite(spot) or not np.isfinite(bid) or bid<=0: continue
            
            m = ((K - spot)/spot*100) if r["type"]=="Put" else ((spot - K)/spot*100)
            t_gap = round((ask - bid) / get_warrant_tick(bid)) if ask > bid else np.nan
            spread = (ask - bid)/bid*100 if ask > bid else np.nan
            iv = implied_volatility(bid, spot, K, T, 0.015, ratio, r["type"])
            delta = bs_greeks(spot, K, T, 0.015, iv, r["type"]) if np.isfinite(iv) else np.nan
            lev = abs(delta) * (spot * ratio / ((bid+ask)/2)) if np.isfinite(delta) else np.nan
            
            # 評分與淘汰
            score = 100 - abs(m)*2 - (spread*10 if np.isfinite(spread) else 50) + (10 if r["days"]>90 else 0)
            passed = (r["issuer"] in REPUTABLE_ISSUERS) and (r["days"] >= min_days) and (-5 <= m <= 10) and (spread <= max_spread) and (r.get("outstanding_ratio", 100) < 80)
            
            r_dict = r.to_dict()
            r_dict.update({"m": m, "t_gap": t_gap, "spread": spread, "iv": iv, "lev": lev, "score": score, "pass": passed})
            res.append(r_dict)
            
        final_df = pd.DataFrame(res)
        if final_df.empty: st.error("無任何資料符合計算條件。"); st.stop()
        
        passed_df = final_df[final_df["pass"]].sort_values("score", ascending=False)
        st.success(f"篩選完成：原始 {len(data)} 檔 ➔ 符合風控 {len(passed_df)} 檔")
        
        if not passed_df.empty:
            for idx, item in enumerate(passed_df.head(8).to_dict('records'), 1):
                badge = f"👑 最佳首選" if idx == 1 else f"候選 #{idx}"
                st.markdown(f"""
                <div class="warrant-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div class="title">{item['name']} ({item['code']})</div>
                        <span class="badge" style="background:#be123c;">{badge}</span>
                    </div>
                    <div class="sub">標的: <b>{item['target_name']}</b> | 券商: <b>{item['issuer']}</b> | 履約價: <b>{item['strike']}</b></div>
                    <hr style="border:0; border-top:1px solid #e2e8f0; margin: 8px 0;">
                    <div class="small"><b>價內外：</b>{item['m']:+.1f}%　<b>剩餘：</b>{item['days']:.0f} 天</div>
                    <div class="small"><b>買賣報價：</b>{item['bid']:.2f} / {item['ask']:.2f}　<b>價差：</b>差 {item['t_gap']:.0f} Tick ({item['spread']:.2f}%)</div>
                    <div class="small"><b>實質槓桿：</b>{item['lev']:.2f}x　<b>IV：</b>{item['iv']*100:.1f}%　<b>流通比：</b>{item['outstanding_ratio']:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.error("⚠️ 皆未通過安全風控門檻（價外過深、天數不足或造市價差過大）。")
            
        st.subheader("🛑 淘汰標的與剔除原因")
        rejected = final_df[~final_df["pass"]].head(10)
        for _, item in rejected.iterrows():
            st.markdown(f"""
            <div class="warrant-card" style="opacity: 0.85;">
                <div class="title" style="color: #64748b !important;">{item['name']} ({item['code']})</div>
                <div class="small" style="color: #dc2626;">未達標 (可能原因: 券商非白名單/流通量大於80/價差過大/深度價外)</div>
            </div>
            """, unsafe_allow_html=True)

