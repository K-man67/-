from __future__ import annotations

from datetime import date, datetime, timedelta
import math
import re
from typing import Any, Optional

import numpy as np
import pandas as pd
import requests
import streamlit as st

# ============================================================
# 權證風控及格雷達 V2.1 (實務專業修正版)
# - 修正「循環驗證」Bug：改用 HV20 計算理論公允價值，客觀評估發行商是否溢價黑心
# - 補齊核心風控：將「流通在外比例 > 80%」與「發行商造市白名單」加入硬性淘汰
# - 效能大幅優化：先過濾靜態指標再發送 MIS 即時行情，杜絕手機端載入超時
# ============================================================

st.set_page_config(
    page_title="權證風控及格雷達 V2.1",
    page_icon="🎯",
    layout="centered",
)

TWSE_OPENAPI = "https://openapi.twse.com.tw/v1"
TWSE_MIS = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"

# -----------------------------
# 手機端優化 CSS
# -----------------------------
st.markdown(
    """
    <style>
    .stButton>button {
        width: 100%;
        border-radius: 9px;
        min-height: 3.1em;
        background: #0d6efd;
        color: #fff;
        font-weight: 800;
        font-size: 16px;
    }
    .warrant-card {
        background: #ffffff !important;
        border: 2px solid #cbd5e1 !important;
        border-radius: 14px;
        padding: 16px;
        margin: 0 0 16px 0;
        box-shadow: 0 4px 12px rgba(0,0,0,.06);
    }
    .title {
        color: #0f172a !important;
        font-size: 18px;
        font-weight: 850;
        margin: 0;
    }
    .sub {
        color: #334155 !important;
        font-size: 13px;
        margin: 5px 0 10px 0;
    }
    .small {
        color: #334155 !important;
        font-size: 13px;
        line-height: 1.6;
    }
    .reason {
        background: #fefce8 !important;
        border-left: 4px solid #ca8a04 !important;
        padding: 12px;
        margin-top: 12px;
        border-radius: 6px;
        color: #713f12 !important;
        font-size: 13px;
        line-height: 1.65;
    }
    .score {
        font-size: 26px;
        font-weight: 900;
        color: #0f172a;
    }
    .badge {
        display: inline-block;
        color: white !important;
        padding: 4px 9px;
        border-radius: 5px;
        font-size: 11px;
        font-weight: 900;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.warning(
    "⚠️ **風控提示**：即使綜合評分獲得 S 級，盤中下單前仍須在券商 App 核對五檔委買賣單量是否正常掛出，嚴禁使用市價單追價。"
)

# ============================================================
# Demo 沙盒數據
# ============================================================
DEMO_DATA = pd.DataFrame(
    [
        {
            "code": "03952T",
            "name": "國巨元大61售02",
            "type": "Put",
            "issuer": "元大",
            "target": "2327",
            "target_name": "國巨",
            "spot": 550.0,
            "strike": 560.0,
            "ratio": 0.10,
            "expiration": (date.today() + timedelta(days=95)).isoformat(),
            "last_trade": (date.today() + timedelta(days=93)).isoformat(),
            "warrant_price": 1.255,
            "bid": 1.25,
            "ask": 1.26,
            "bid_qty": 180,
            "ask_qty": 175,
            "volume": 1800,
            "outstanding_ratio": 35.0,
            "iv": 0.33,
        },
        {
            "code": "03958T",
            "name": "國巨凱基62售01",
            "type": "Put",
            "issuer": "凱基",
            "target": "2327",
            "target_name": "國巨",
            "spot": 550.0,
            "strike": 548.0,
            "ratio": 0.10,
            "expiration": (date.today() + timedelta(days=110)).isoformat(),
            "last_trade": (date.today() + timedelta(days=108)).isoformat(),
            "warrant_price": 1.155,
            "bid": 1.15,
            "ask": 1.16,
            "bid_qty": 200,
            "ask_qty": 195,
            "volume": 2200,
            "outstanding_ratio": 22.0,
            "iv": 0.31,
        },
        {
            "code": "03960T",
            "name": "國巨國泰61售05",
            "type": "Put",
            "issuer": "國泰",
            "target": "2327",
            "target_name": "國巨",
            "spot": 550.0,
            "strike": 570.0,
            "ratio": 0.10,
            "expiration": (date.today() + timedelta(days=80)).isoformat(),
            "last_trade": (date.today() + timedelta(days=78)).isoformat(),
            "warrant_price": 1.405,
            "bid": 1.40,
            "ask": 1.41,
            "bid_qty": 160,
            "ask_qty": 155,
            "volume": 1500,
            "outstanding_ratio": 41.5,
            "iv": 0.36,
        },
        {
            "code": "03999T",
            "name": "國巨群益5C售03",
            "type": "Put",
            "issuer": "群益",
            "target": "2327",
            "target_name": "國巨",
            "spot": 550.0,
            "strike": 400.0,
            "ratio": 0.10,
            "expiration": (date.today() + timedelta(days=35)).isoformat(),
            "last_trade": (date.today() + timedelta(days=33)).isoformat(),
            "warrant_price": 0.175,
            "bid": 0.15,
            "ask": 0.20,
            "bid_qty": 5,
            "ask_qty": 20,
            "volume": 300,
            "outstanding_ratio": 88.0,
            "iv": 0.75,
        },
        {
            "code": "03619T",
            "name": "華邦電國泰61售08",
            "type": "Put",
            "issuer": "國泰",
            "target": "2344",
            "target_name": "華邦電",
            "spot": 162.0,
            "strike": 170.0,
            "ratio": 0.10,
            "expiration": (date.today() + timedelta(days=130)).isoformat(),
            "last_trade": (date.today() + timedelta(days=128)).isoformat(),
            "warrant_price": 1.115,
            "bid": 1.11,
            "ask": 1.12,
            "bid_qty": 270,
            "ask_qty": 268,
            "volume": 1400,
            "outstanding_ratio": 28.5,
            "iv": 0.34,
        },
    ]
)

REPUTABLE_ISSUERS = ["元大", "凱基", "國泰", "富邦", "統一", "台新"]


# ============================================================
# 數值輔助與工具函式
# ============================================================
def safe_float(x: Any) -> float:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    s = str(x).strip().replace(",", "").replace("%", "")
    if s in {"", "-", "--", "None", "nan", "NaN"}:
        return np.nan
    try:
        return float(s)
    except Exception:
        return np.nan


def first_value(row: dict, candidates: list[str], default=np.nan):
    for key in candidates:
        if key in row and str(row[key]).strip() not in {"", "-", "--", "None"}:
            return row[key]
    return default


def roc_to_date(x: Any) -> Optional[date]:
    if x is None:
        return None
    digits = re.sub(r"\D", "", str(x))
    try:
        if len(digits) == 7:
            return date(int(digits[:3]) + 1911, int(digits[3:5]), int(digits[5:7]))
        if len(digits) == 8:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    except Exception:
        return None
    return None


def get_warrant_tick(price: float) -> float:
    if not np.isfinite(price):
        return np.nan
    if price < 5:
        return 0.01
    if price < 10:
        return 0.05
    if price < 50:
        return 0.10
    if price < 100:
        return 0.50
    if price < 500:
        return 1.00
    return 5.00


def norm_type(x: Any) -> str:
    s = str(x).lower()
    if any(k in s for k in ["認售", "put", "bear", "熊"]):
        return "Put"
    if any(k in s for k in ["認購", "call", "bull", "牛"]):
        return "Call"
    return ""


def normalize_name(x: Any) -> str:
    return str(x).strip() if x is not None else ""


# ============================================================
# API 資料抓取模組
# ============================================================
@st.cache_data(ttl=300, show_spinner=False)
def fetch_json(url: str, params: Optional[dict] = None) -> Any:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
    }
    r = requests.get(url, params=params, headers=headers, timeout=12)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=600, show_spinner=False)
def fetch_warrant_basic() -> pd.DataFrame:
    url = f"{TWSE_OPENAPI}/opendata/t187ap37_L"
    raw = fetch_json(url)

    if not isinstance(raw, list):
        raise ValueError("TWSE 權證基本資料回傳格式錯誤。")

    rows = []
    for r in raw:
        code = normalize_name(
            first_value(r, ["權證代號", "證券代號", "Code", "code"], "")
        )
        if not code:
            continue

        target = normalize_name(
            first_value(
                r, ["標的代號", "標的證券代號", "標的代碼", "權證標的代碼"], ""
            )
        )
        target_name = normalize_name(
            first_value(r, ["標的名稱", "標的證券名稱", "標的名稱 "], "")
        )
        issuer = normalize_name(
            first_value(r, ["發行人", "發行機構名稱", "發行商"], "")
        )
        name = normalize_name(
            first_value(r, ["權證名稱", "證券名稱", "簡稱", "權證簡稱"], code)
        )
        wtype = norm_type(
            first_value(r, ["權證類型", "權證型態", "類型", "WarrantType"], "")
        )
        strike = safe_float(
            first_value(r, ["履約價", "履約價格", "履約點數"], np.nan)
        )
        ratio = safe_float(
            first_value(r, ["行使比例", "行使比率", "履約比例"], np.nan)
        )
        if np.isfinite(ratio) and ratio > 1:
            ratio /= 100.0

        expiration = roc_to_date(first_value(r, ["到期日", "到期日期"], None))
        last_trade = roc_to_date(
            first_value(r, ["最後交易日", "最後交易日期"], None)
        )

        latest_qty = safe_float(
            first_value(r, ["最新權證數量", "最新權證數量(仟單位)"], np.nan)
        )
        issue_qty = safe_float(
            first_value(r, ["發行時權證數量", "發行時權證數量(仟單位)"], np.nan)
        )

        outstanding_ratio = np.nan
        if np.isfinite(latest_qty) and np.isfinite(issue_qty) and issue_qty > 0:
            outstanding_ratio = latest_qty / issue_qty * 100

        rows.append(
            {
                "code": code,
                "name": name,
                "type": wtype,
                "issuer": issuer,
                "target": target,
                "target_name": target_name,
                "strike": strike,
                "ratio": ratio,
                "expiration": expiration.isoformat() if expiration else "",
                "last_trade": last_trade.isoformat() if last_trade else "",
                "outstanding_ratio": outstanding_ratio,
            }
        )

    df = pd.DataFrame(rows)
    return df


@st.cache_data(ttl=20, show_spinner=False)
def fetch_mis_quotes(codes: tuple[str, ...]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame()

    ex = "|".join(f"tse_{c}.tw" for c in codes)
    try:
        raw = fetch_json(TWSE_MIS, params={"ex_ch": ex})
    except Exception:
        return pd.DataFrame()

    data = raw.get("msgArray", []) if isinstance(raw, dict) else []
    rows = []

    for r in data:
        code = normalize_name(r.get("c", ""))
        if not code:
            continue

        def level_val(prefix: str, idx: int) -> float:
            val = r.get(prefix, "")
            if isinstance(val, str) and "_" in val:
                parts = val.split("_")
                if len(parts) > idx:
                    return safe_float(parts[idx])
            return safe_float(val)

        rows.append(
            {
                "code": code,
                "last": safe_float(r.get("z")),
                "bid": level_val("b", 0),
                "ask": level_val("a", 0),
                "bid_qty": level_val("g", 0),
                "ask_qty": level_val("f", 0),
                "volume": safe_float(r.get("v")),
            }
        )
    return pd.DataFrame(rows)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock_history(stock_code: str) -> pd.DataFrame:
    today = date.today()
    frames = []
    months = [
        (today.year, today.month),
        (
            today.year if today.month > 1 else today.year - 1,
            today.month - 1 if today.month > 1 else 12,
        ),
    ]

    for yy, mm in months:
        url = f"{TWSE_OPENAPI}/exchangeReport/STOCK_DAY"
        try:
            raw = fetch_json(
                url, params={"stockNo": stock_code, "date": f"{yy}{mm:02d}01"}
            )
            data = raw.get("data", []) if isinstance(raw, dict) else raw
            if data:
                df = pd.DataFrame(
                    data,
                    columns=[
                        "日期",
                        "成交股數",
                        "成交金額",
                        "開盤價",
                        "最高價",
                        "最低價",
                        "收盤價",
                        "漲跌價差",
                        "成交筆數",
                    ],
                )
                frames.append(df)
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df["close"] = pd.to_numeric(
        df["收盤價"].astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )
    df["date"] = pd.to_datetime(
        df["日期"].astype(str).str.replace("/", "-", regex=False),
        errors="coerce",
    )
    return df.dropna(subset=["close", "date"]).sort_values("date")


# ============================================================
# Black-Scholes 評價與分析模組
# ============================================================
def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def bs_price(
    S: float, K: float, T: float, r: float, sigma: float, kind: str
) -> float:
    if min(S, K, T, sigma) <= 0:
        return np.nan
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (
        sigma * math.sqrt(T)
    )
    d2 = d1 - sigma * math.sqrt(T)
    if kind == "Call":
        return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)


def bs_greeks(
    S: float, K: float, T: float, r: float, sigma: float, kind: str
) -> dict[str, float]:
    if min(S, K, T, sigma) <= 0:
        return {
            "delta": np.nan,
            "gamma": np.nan,
            "theta": np.nan,
            "vega": np.nan,
        }
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (
        sigma * math.sqrt(T)
    )
    d2 = d1 - sigma * math.sqrt(T)
    if kind == "Call":
        delta = norm_cdf(d1)
        theta = (
            -S * norm_pdf(d1) * sigma / (2 * math.sqrt(T))
            - r * K * math.exp(-r * T) * norm_cdf(d2)
        ) / 365.0
    else:
        delta = norm_cdf(d1) - 1
        theta = (
            -S * norm_pdf(d1) * sigma / (2 * math.sqrt(T))
            + r * K * math.exp(-r * T) * norm_cdf(-d2)
        ) / 365.0
    gamma = norm_pdf(d1) / (S * sigma * math.sqrt(T))
    vega = S * norm_pdf(d1) * math.sqrt(T) / 100.0
    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega}


def implied_volatility(
    market_warrant_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    ratio: float,
    kind: str,
) -> float:
    if not all(np.isfinite(x) for x in [market_warrant_price, S, K, T, r, ratio]):
        return np.nan
    if market_warrant_price <= 0 or ratio <= 0 or S <= 0 or K <= 0 or T <= 0:
        return np.nan

    option_market = market_warrant_price / ratio
    lo, hi = 0.001, 4.0
    for _ in range(60):
        mid = (lo + hi) / 2
        p_mid = bs_price(S, K, T, r, mid, kind)
        if not np.isfinite(p_mid):
            return np.nan
        if p_mid > option_market:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def compute_hv(stock_history: pd.DataFrame, window: int = 20) -> float:
    if stock_history.empty or len(stock_history) < window + 1:
        return np.nan
    close = stock_history["close"].astype(float)
    ret = np.log(close / close.shift(1)).dropna()
    if len(ret) < window:
        return np.nan
    return float(ret.tail(window).std() * math.sqrt(252))


# ============================================================
# 風控門檻與評分卡邏輯
# ============================================================
def hard_filter(
    row: pd.Series, min_days: int, max_spread: float, max_abs_m: float
) -> tuple[bool, list[str]]:
    reasons = []

    if row.get("issuer") not in REPUTABLE_ISSUERS:
        reasons.append(f"發行商({row.get('issuer')})非造市白名單")

    if not np.isfinite(row["days"]) or row["days"] < min_days:
        reasons.append(f"剩餘天數({row['days']:.0f}天) < {min_days}天")

    if np.isfinite(row["abs_moneyness"]) and row["abs_moneyness"] > max_abs_m:
        reasons.append(f"價內外偏離({row['abs_moneyness']:.1f}%) > {max_abs_m}%")

    if np.isfinite(row["spread"]) and row["spread"] > max_spread:
        reasons.append(f"買賣價差({row['spread']:.1f}%) > {max_spread}%")

    if (
        np.isfinite(row.get("outstanding_ratio", np.nan))
        and row["outstanding_ratio"] >= 80.0
    ):
        reasons.append(
            f"流通比({row['outstanding_ratio']:.1f}%) >= 80% (券商斷掛/散戶溢價)"
        )

    if not np.isfinite(row["bid"]) or row["bid"] <= 0:
        reasons.append("買一(Bid)價格無效或造市商撤單")

    return len(reasons) == 0, reasons


def score_closeness(m: float) -> float:
    return max(0.0, 100.0 - abs(m) * 8.0) if np.isfinite(m) else 0


def score_days(days: float) -> float:
    if not np.isfinite(days):
        return 0
    if 75 <= days <= 150:
        return 100
    if 60 <= days < 75:
        return 85
    return 50


def score_spread(spread: float) -> float:
    if not np.isfinite(spread):
        return 0
    if spread <= 1.0:
        return 100
    if spread <= 2.0:
        return 85
    return 40


def score_iv_vs_hv(iv: float, hv: float) -> float:
    if not np.isfinite(iv) or not np.isfinite(hv) or hv <= 0:
        return 60
    ratio = iv / hv
    if ratio <= 1.10:
        return 100
    if ratio <= 1.25:
        return 85
    if ratio <= 1.45:
        return 60
    return 30


def score_leverage(lev: float) -> float:
    if not np.isfinite(lev):
        return 50
    if 4.0 <= lev <= 7.5:
        return 100
    if 3.0 <= lev < 4.0 or 7.5 < lev <= 9.0:
        return 80
    return 45


def score_premium(premium: float) -> float:
    if not np.isfinite(premium):
        return 50
    a = abs(premium)
    if a <= 5:
        return 100
    if a <= 12:
        return 80
    if a <= 20:
        return 60
    return 30


def grade(score: float) -> tuple[str, str]:
    if score >= 90:
        return "S", "#be123c"
    if score >= 80:
        return "A", "#16a34a"
    if score >= 70:
        return "B", "#2563eb"
    if score >= 60:
        return "C", "#ca8a04"
    return "淘汰", "#64748b"


def build_analysis(
    df: pd.DataFrame, risk_free: float, hv20: float
) -> pd.DataFrame:
    out = df.copy()
    today = date.today()

    out["expiration_dt"] = pd.to_datetime(
        out["expiration"], errors="coerce"
    ).dt.date
    out["last_trade_dt"] = pd.to_datetime(
        out["last_trade"], errors="coerce"
    ).dt.date
    out["days"] = out["expiration_dt"].apply(
        lambda d: (d - today).days if isinstance(d, date) else np.nan
    )

    # 統一以現價 (spot) 為分母
    out["moneyness"] = out.apply(
        lambda r: (
            ((r["strike"] - r["spot"]) / r["spot"] * 100)
            if r["type"] == "Put"
            else ((r["spot"] - r["strike"]) / r["spot"] * 100)
        ),
        axis=1,
    )
    out["abs_moneyness"] = out["moneyness"].abs()

    # 精確計算真實 Tick 級距
    def calc_tick(r):
        if (
            not np.isfinite(r["bid"])
            or not np.isfinite(r["ask"])
            or r["bid"] <= 0
        ):
            return np.nan, np.nan
        t = get_warrant_tick(r["bid"])
        return round((r["ask"] - r["bid"]) / t), (
            (r["ask"] - r["bid"]) / r["bid"] * 100
        )

    gaps = out.ap
