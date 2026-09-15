from datetime import date
import pandas as pd
import streamlit as st

st.set_page_config(page_title="權證及格快篩", layout="centered")

# 強制固定高對比配色（防止手機深色模式造成黑底黑字）
st.markdown(
    """
    <style>
    .stButton>button {width: 100%; border-radius: 8px; height: 3.2em; background-color: #0d6efd; color: #ffffff; font-weight: bold; font-size: 16px;}
    .warrant-card {
        background-color: #ffffff !important; 
        border: 2px solid #cbd5e1 !important; 
        border-radius: 12px; 
        padding: 16px; 
        margin-bottom: 16px; 
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.08);
    }
    .warrant-title {color: #0f172a !important; font-size: 18px; font-weight: 800; margin: 0;}
    .warrant-sub {color: #334155 !important; font-size: 14px; margin: 6px 0 10px 0;}
    .stat-text {color: #0f172a !important; font-size: 14px; font-weight: 600;}
    .reason-box {
        background-color: #fefce8 !important; 
        border-left: 4px solid #ca8a04 !important; 
        padding: 12px; 
        margin-top: 12px; 
        border-radius: 6px; 
        color: #713f12 !important; 
        font-size: 13px; 
        line-height: 1.6;
    }
    .badge-pass {
        background-color: #16a34a !important; 
        color: #ffffff !important; 
        padding: 3px 8px; 
        border-radius: 4px; 
        font-size: 12px; 
        font-weight: bold;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("🎯 權證及格快篩雷達")

# 輸入區
query = st.text_input(
    "查詢標的代碼 / 權證名稱",
    value="2327",
    placeholder="例: 2344、2327、國巨、華邦電",
)
w_type = st.radio(
    "選擇操作方向", ["認售 (Put)", "認購 (Call)"], horizontal=True
)
target_type = "Put" if "認售" in w_type else "Call"

# 擴充資料庫：包含多檔合格與淘汰標的
DATA = pd.DataFrame(
    [
        # --- 國巨認售 (多檔及格展示) ---
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
            "id": "03958T",
            "name": "國巨凱基62售01",
            "type": "Put",
            "issuer": "凱基",
            "strike": 545.0,
            "days": 110,
            "out_ratio": 22.0,
            "bid": 1.15,
            "ask": 1.16,
            "leverage": 6.2,
        },
        {
            "target": "2327",
            "target_name": "國巨",
            "spot": 550.0,
            "id": "03960T",
            "name": "國巨國泰61售05",
            "type": "Put",
            "issuer": "國泰",
            "strike": 570.0,
            "days": 80,
            "out_ratio": 41.5,
            "bid": 1.40,
            "ask": 1.41,
            "leverage": 5.1,
        },
        {
            "target": "2327",
            "target_name": "國巨",
            "spot": 550.0,
            "id": "03999T",
            "name": "國巨群益5C售03",
            "type": "Put",
            "issuer": "群益",
            "strike": 400.0,
            "days": 35,
            "out_ratio": 88.0,
            "bid": 0.15,
            "ask": 0.20,
            "leverage": 12.0,
        },  # 淘汰
        # --- 華邦電 (多檔展示) ---
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
            "id": "03622T",
            "name": "華邦電元大61售05",
            "type": "Put",
            "issuer": "元大",
            "strike": 165.0,
            "days": 105,
            "out_ratio": 33.0,
            "bid": 1.05,
            "ask": 1.06,
            "leverage": 5.6,
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
        },  # 淘汰
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
        qualified_list = []
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
                row_data = row.to_dict()
                row_data["moneyness"] = moneyness
                row_data["spread_ratio"] = spread_ratio
                qualified_list.append(row_data)

        if qualified_list:
            st.success(
                f"🎉 共篩選出 {len(qualified_list)} 檔完全合格的安全權證："
            )
            for item in qualified_list:
                m_val = item["moneyness"]
                st.markdown(
                    f"""
                <div class="warrant-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h3 class="warrant-title">{item['name']} ({item['id']})</h3>
                        <span class="badge-pass">及格首選</span>
                    </div>
                    <p class="warrant-sub">標的: <b>{item['target_name']}</b> | 履約價: <b>{item['strike']}</b> | 實質槓桿: <b>{item['leverage']}倍</b></p>
                    <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 10px 0;">
                    <div style="display:flex; justify-content:space-between; margin-bottom: 8px;">
                        <span class="stat-text">價內外: <b style="color:{'#dc2626' if m_val > 0 else '#16a34a'};">{m_val:+.1f}%</b></span>
                        <span class="stat-text">剩餘天數: <b>{item['days']} 天</b></span>
                        <span class="stat-text">買/賣價: <b>{item['bid']} / {item['ask']}</b></span>
                    </div>
                    <div class="reason-box">
                        <b>📋 推薦理由與風控核對：</b><br>
                        • <b>履約位置：</b>處於價平甜蜜區（{m_val:+.1f}%），連動敏銳度最佳。<br>
                        • <b>時間耗損：</b>天數充足（{item['days']}天 > 60天門檻），時間價值流失平緩。<br>
                        • <b>摩擦成本：</b>買賣價差僅 {item['spread_ratio']:.2f}%（差 1 tick），進出極低成本。<br>
                        • <b>籌碼安全：</b>券商庫存充足（流通比 {item['out_ratio']}%），無散戶溢價追高風險。
                    </div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
        else:
            st.error(
                "⚠️ 該標的現存權證皆未達及格標準（深度價外、天數不足或散戶溢價過高），基於風控一律不予推薦。"
            )
