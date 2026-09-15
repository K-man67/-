from datetime import date, timedelta
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
    .badge-alt {
        background-color: #64748b !important; 
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
st.caption(
    "⚠️ 目前資料為示範用固定資料（DATA 內寫死），尚未串接即時行情或權證基本資料 API，"
    "正式使用前請先接上真實資料源；本工具也尚未納入隱含波動率(IV)比較。"
)

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

# 擴充資料庫：包含多檔合格與淘汰標的（示範用，正式版請改為即時資料源）
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

# 註：此清單是主觀認定「造市品質較穩定」的發行商，屬於人工 heuristic，
# 會把群益等其他發行商整批排除，不代表其造市品質必然較差。
# 建議未來改用實際造市數據（如平均價差、委買深度、歷史履約成交量）動態判斷，
# 而非固定名單。
QUALIFIED_ISSUERS = ["元大", "凱基", "國泰", "富邦", "統一", "台新"]


def get_tick_size(price: float) -> float:
    """依台股/權證價格級距對應的跳動單位。
    這張表沿用交易所常見的級距設計，若交易所調整過級距，請自行更新。
    """
    if price < 10:
        return 0.01
    elif price < 50:
        return 0.05
    elif price < 100:
        return 0.1
    elif price < 500:
        return 0.5
    elif price < 1000:
        return 1.0
    else:
        return 5.0


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

            # 價平位置：Put / Call 統一以現價(spot)為分母，正值代表價內。
            # 原版 Call 用 strike 當分母，會讓兩種方向的門檻基準不一致，這裡修正。
            if target_type == "Put":
                moneyness = (strike - spot) / spot * 100
            else:
                moneyness = (spot - strike) / spot * 100

            spread_ratio = (row["ask"] - row["bid"]) / row["bid"] * 100

            # 實際跳動點數，取代原版一律寫死「差1 tick」的文案
            tick = get_tick_size(row["bid"])
            tick_count = round((row["ask"] - row["bid"]) / tick)

            # 用剩餘天數換算實際到期日，方便使用者對照
            expiry_date = date.today() + timedelta(days=int(row["days"]))

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
                row_data["tick_count"] = tick_count
                row_data["expiry_date"] = expiry_date
                qualified_list.append(row_data)

        # 依「最接近價平」排序，價差比例當次要排序，最值得優先看的排最前面
        qualified_list.sort(key=lambda x: (abs(x["moneyness"]), x["spread_ratio"]))

        if qualified_list:
            st.success(
                f"🎉 共篩選出 {len(qualified_list)} 檔完全合格的安全權證（依價平位置排序）："
            )
            for idx, item in enumerate(qualified_list):
                m_val = item["moneyness"]
                badge_class = "badge-pass" if idx == 0 else "badge-alt"
                badge_text = "最佳候選" if idx == 0 else f"候選 #{idx + 1}"
                tick_text = (
                    f"僅 {item['tick_count']} 個跳動點"
                    if item["tick_count"] <= 1
                    else f"約 {item['tick_count']} 個跳動點"
                )
                st.markdown(
                    f"""
                <div class="warrant-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h3 class="warrant-title">{item['name']} ({item['id']})</h3>
                        <span class="{badge_class}">{badge_text}</span>
                    </div>
                    <p class="warrant-sub">標的: <b>{item['target_name']}</b> | 履約價: <b>{item['strike']}</b> | 實質槓桿: <b>{item['leverage']}倍</b>（示範值，正式版建議改為即時計算）</p>
                    <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 10px 0;">
                    <div style="display:flex; justify-content:space-between; margin-bottom: 8px;">
                        <span class="stat-text">價內外: <b style="color:{'#dc2626' if m_val > 0 else '#16a34a'};">{m_val:+.1f}%</b></span>
                        <span class="stat-text">剩餘天數: <b>{item['days']} 天</b>（約 {item['expiry_date']:%Y-%m-%d}）</span>
                        <span class="stat-text">買/賣價: <b>{item['bid']} / {item['ask']}</b></span>
                    </div>
                    <div class="reason-box">
                        <b>📋 推薦理由與風控核對：</b><br>
                        • <b>履約位置：</b>價平位置 {m_val:+.1f}%，落於設定的甜蜜區間內。<br>
                        • <b>時間耗損：</b>天數充足（{item['days']}天 > 60天門檻），時間價值流失平緩。<br>
                        • <b>摩擦成本：</b>買賣價差 {item['spread_ratio']:.2f}%（{tick_text}），進出成本低。<br>
                        • <b>籌碼安全：</b>券商庫存充足（流通比 {item['out_ratio']}%），無散戶溢價追高風險。<br>
                        • <b>注意：</b>本篩選尚未納入隱含波動率(IV)比較，建議串接真實資料後補上此項再做最終判斷。
                    </div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
        else:
            st.error(
                "⚠️ 該標的現存權證皆未達及格標準（深度價外、天數不足或散戶溢價過高），基於風控一律不予推薦。"
            )
