from fredapi import Fred
import pandas as pd
from datetime import datetime, timedelta

def get_comprehensive_data(api_key):
    fred = Fred(api_key=api_key)
    now = datetime.now()
    
    # --- 輔助函式庫 ---
    def fetch_yoy(s_id):
        try:
            df = fred.get_series(s_id, observation_start=(now - timedelta(days=1095))).dropna()
            val = df.iloc[-1]
            idx_1y = df.index.get_indexer([df.index[-1] - pd.DateOffset(years=1)], method='nearest')[0]
            yoy = ((val - df.iloc[idx_1y]) / df.iloc[idx_1y]) * 100
            # 判斷趨勢是否反彈 (YoY now > YoY 3m ago)
            idx_3m = df.index.get_indexer([df.index[-1] - pd.DateOffset(months=3)], method='nearest')[0]
            val_3m = df.iloc[idx_3m]
            idx_3m_1y = df.index.get_indexer([df.index[idx_3m] - pd.DateOffset(years=1)], method='nearest')[0]
            yoy_3m = ((val_3m - df.iloc[idx_3m_1y]) / df.iloc[idx_3m_1y]) * 100
            return {"val": round(val, 2), "yoy": round(yoy, 2), "rebound": yoy > yoy_3m}
        except: return None

    def fetch_peak(s_id, years=2, type='min'):
        try:
            df = fred.get_series(s_id, observation_start=(now - timedelta(days=years*365+90))).dropna()
            latest = df.iloc[-1]
            if type == 'min':
                peak_val = df.min()
                pct = ((latest - peak_val) / peak_val) * 100
            else:
                peak_val = df.max()
                pct = ((latest - peak_val) / peak_val) * 100
            return {"val": round(latest, 2), "pct": round(pct, 2)}
        except: return None

    # --- 抓取全數據 ---
    data = {
        "fed": fetch_yoy("FEDFUNDS"),
        "icsa": fetch_peak("ICSA", 2, 'min'),
        "retail": fetch_yoy("RSAFS"),
        "dgorder": fetch_yoy("DGORDER"),
        "payems": fetch_yoy("PAYEMS"),
        "pnfi": fetch_yoy("PNFI"),
        "prfi": fetch_yoy("PRFI"),
        "cpi": fetch_yoy("CPIAUCSL"),
        "yield_curve": fetch_yoy("T10Y2Y"),
        "sentiment": fetch_peak("UMCSENT", 1, 'max'),
        "pce": fetch_yoy("PCE"),
        "real_pce": fetch_yoy("PCEC96"),
        "gpdic1": fetch_yoy("GPDIC1"),
        "pmi": fetch_yoy("NAPM"),
    }

    # --- 週期評分邏輯 ---
    scores = {"recovery": 0, "growth": 0, "boom": 0, "recession": 0}
    if data['fed'] and data['fed']['val'] < 2.5: scores['recovery'] += 1
    if data['icsa'] and data['icsa']['pct'] < 5: scores['recovery'] += 1
    if data['payems'] and data['payems']['yoy'] > 1.0: scores['growth'] += 1
    if data['yield_curve'] and data['yield_curve']['val'] < 0: scores['boom'] += 1
    if data['real_pce'] and data['real_pce']['yoy'] < 1.0: scores['recession'] += 1

    # --- 最終判定 ---
    if scores['recession'] >= 1: verdict = "🥶 衰退期"
    elif scores['boom'] >= 1: verdict = "🔥 榮景期 (轉折預警)"
    elif scores['growth'] >= 2: verdict = "📈 穩定成長期"
    else: verdict = "🌱 復甦過渡期"

    return {"timestamp": now.strftime("%Y-%m-%d %H:%M"), "data": data, "scores": scores, "verdict": verdict}
