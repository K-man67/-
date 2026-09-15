from datetime import date
import pandas as pd
import streamlit as st

st.set_page_config(page_title="權證及格快篩", layout="centered")

# 手機端客製樣式
st.markdown(
    """
    <style>
    .stButton>button {width: 100%; border-radius: 8px; height: 3em; background-color: #0066cc; color: white;}
    .warrant-card {border: 1px solid #333; border-radius: 10px; padding: 15px; margin-bottom: 15px; background-color: #1e1e1e;}
    .reason-box {background-color: #2b2b2b; border-left: 4px solid #f39c12; padding: 10px; margin-top: 10px; border-radius: 4px; font-size: 13px;}
    </style>
""",
    unsafe_allow_html=True,
)

st.title("🎯 權證及格快篩雷達")

# 1. 極簡輸入主頁
query = st.text_input(
    "查詢標的代碼 / 名稱",
    value="2344",
    placeholder="輸入代碼或名稱 (如: 2344、華邦電、國巨)",
)
w_type = st.radio(
    "選擇權證方向", ["認售 (Put)", "認購 (Call)"], horizontal=True
)
target_type = "Put" if "認售" in w_type else "Call"

# 權證資料庫 (實務可外接 API)
DATA = pd.DataFrame(
    [
        {
            "target": "2344",
            "target_name": "華邦電",
            "spot": 162.0,
            "id": "03619T",
            "name": "華邦電國泰61售08",
            "type": "Put",
            "issuer": "國泰",
            "strike": 170.0,
            "days": 130,
            "out_ratio": 28.5,
            "bid": 1.11,
            "ask": 1.12,
            "leverage": 5.2,
        },
        {
            "target": "2344",
            "target_name": "華邦電",
            "spot": 162.0,
            "id": "03070T",
            "name": "華邦電群益5C售01",
            "type": "Put",
            "issuer": "群益",
            "strike": 60.0,
            "days": 40,
            "out_ratio": 92.0,
            "bid": 0.02,
            "ask": 0.05,
            "leverage": 12.0,
        },
        {
            "target": "2327",
            "target_name": "國巨",
            "spot": 550.0,
            "id": "03952T",
            "name": "國巨元大61售02",
            "type": "Put",
            "issuer": "元大",
            "strike": 560.0,
            "days": 95,
            "out_ratio": 35.0,
            "bid": 1.25,
            "ask": 1.26,
            "leverage": 5.8,
        },
        {
            "target": "2327",
            "target_name": "國巨",
            "spot": 550.0,
            "id": "05123",
            "name": "國巨凱基62購01",
            "type": "Call",
            "issuer": "凱基",
            "strike": 565.0,
            "days": 85,
            "out_ratio": 41.2,
            "bid": 1.85,
            "ask": 1.87,
            "leverage": 6.1,
        },
    ]
)

QUALIFIED_ISSUERS = ["元大", "凱基", "國泰", "富邦", "統一", "台新"]

if st.button("開始安全篩選"):
    q = query.strip().upper()
    matched = DATA[
        (
            (DATA["target"] == q)
            | (DATA["target_name"] == q)
            | (DATA["name"].str.contains(q))
        )
        & (DATA["type"] == target_type)
    ].copy()

    if matched.empty:
        st.warning(f"查無標的【{query}】之權證資料。")
    else:
        found_any = False
        for _, row in matched.iterrows():
            spot = row["spot"]
            strike = row["strike"]
            moneyness = (
                ((strike - spot) / spot * 100)
                if target_type == "Put"
                else ((spot - strike) / strike * 100)
            )
            spread_ratio = (row["ask"] - row["bid"]) / row["bid"] * 100

            # 及格門檻一票否決
            if (
                row["issuer"] in QUALIFIED_ISSUERS
                and row["days"] >= 60
                and -5.0 <= moneyness <= 10.0
                and row["out_ratio"] < 80.0
                and spread_ratio <= 2.0
            ):
                found_any = True
                # 渲染及格卡片
                st.markdown(
                    f"""
                <div class="warrant-card">
                    <h3 style="margin:0; color:#58a6ff;">{row['name']} ({row['id']})</h3>
                    <p style="margin:5px 0; color:#8b949e;">現價標的: {row['target_name']} | 履約價: {row['strike']} | 實質槓桿: {row['leverage']}倍</p>
                    <hr style="border-color:#30363d;">
                    <div style="display:flex; justify-content:space-between; font-size:14px;">
                        <span>價內外: <b>{moneyness:+.1f}%</b></span>
                        <span>剩餘天數: <b>{row['days']} 天</b></span>
                        <span>買賣報價: <b>{row['bid']} / {row['ask']}</b></span>
                    </div>
                    <div class="reason-box">
                        <b>📋 系統推薦理由：</b><br>
                        • 處於價平/微價內甜蜜點，現股一動立即緊咬連動。<br>
                        • 剩餘天數達 {row['days']} 天（遠高於60天門檻），每日時間耗損極低。<br>
                        • 買賣價差比僅 {spread_ratio:.2f}% (差1 tick)，進出場極低摩擦成本。<br>
                        • 發行商庫存充足 (流通比 {row['out_ratio']}%)，無散戶超額溢價踩踏風險。
                    </div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

        if not found_any:
            st.error(
                "⚠️ 該標的現存權證皆未達安全及格標準（深度價外、天數不足或散戶溢價過高），基於風控不予推薦。"
            )
