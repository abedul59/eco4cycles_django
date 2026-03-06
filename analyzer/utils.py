from fredapi import Fred
import pandas as pd
from datetime import datetime, timedelta

def get_comprehensive_data(api_key):
    try:
        fred = Fred(api_key=api_key)
        now = datetime.now()

        # --- 爬蟲輔助函式 (自動處理遺漏值與時間推移) ---
        def fetch_annual_growth(series_id):
            try:
                data = fred.get_series(series_id, observation_start=(now - timedelta(days=1825))).dropna()
                if len(data) < 4: return None
                idx_1y = data.index.get_indexer([data.index[-1] - pd.DateOffset(years=1)], method='nearest')[0]
                yoy = ((data.iloc[-1] - data.iloc[idx_1y]) / data.iloc[idx_1y]) * 100
                return {"latest": round(data.iloc[-1], 2), "yoy": round(yoy, 2)}
            except: return None

        def fetch_trend_data(series_id, days=365):
            try:
                data = fred.get_series(series_id, observation_start=(now - timedelta(days=days))).dropna()
                data_d = data if len(data) < 90 else data.resample('W').last()
                val_3m_ago = data_d.iloc[-13] if len(data_d) >= 13 else data_d.iloc[0]
                change = ((data_d.iloc[-1] - val_3m_ago) / val_3m_ago) * 100
                return {"latest": round(data_d.iloc[-1], 2), "change_3m": round(change, 2), "trend_down": change < 0}
            except: return None

        def fetch_yoy_data(series_id):
            try:
                data = fred.get_series(series_id, observation_start=(now - timedelta(days=1095))).dropna()
                data_m = data.resample('ME').last() # 相容新版 Pandas
                if len(data_m) < 16: return None
                yoy_now = ((data_m.iloc[-1] - data_m.iloc[-13]) / data_m.iloc[-13]) * 100
                yoy_3m_ago = ((data_m.iloc[-4] - data_m.iloc[-16]) / data_m.iloc[-16]) * 100
                return {"latest": round(data_m.iloc[-1], 2), "yoy_now": round(yoy_now, 2), "trend_rebound": yoy_now > yoy_3m_ago}
            except: return None

        def fetch_peak_reversal(series_id, lookback_years=3):
            try:
                start_date = (now - timedelta(days=lookback_years*365 + 90)).strftime('%Y-%m-%d')
                data = fred.get_series(series_id, observation_start=start_date).dropna()
                if len(data) < 3: return None
                cutoff_date = data.index[-1] - pd.DateOffset(years=lookback_years)
                period_data = data[data.index >= cutoff_date]
                if len(period_data) == 0: period_data = data 
                latest = period_data.iloc[-1]
                return {
                    "latest": round(latest, 2), 
                    "pct_from_min": round(((latest - period_data.min())/period_data.min())*100, 2), 
                    "pct_from_max": round(((latest - period_data.max())/period_data.max())*100, 2)
                }
            except: return None

        def fetch_saar_data(series_id):
            try:
                data = fred.get_series(series_id, observation_start=(now - timedelta(days=730))).dropna()
                data_q = data.resample('QE').last() 
                if len(data_q) < 3: return None
                saar_now = ((data_q.iloc[-1] / data_q.iloc[-2])**4 - 1) * 100
                saar_prev = ((data_q.iloc[-2] / data_q.iloc[-3])**4 - 1) * 100
                return {"latest": round(data_q.iloc[-1], 2), "saar_now": round(saar_now, 2), "rebounding": saar_now > saar_prev}
            except: return None

        # --- 抓取所有 20 項資料 ---
        fed = fetch_trend_data('FEDFUNDS')
        icsa_peak = fetch_peak_reversal('ICSA', 2)
        payems = fetch_annual_growth('PAYEMS')
        retail_yoy = fetch_yoy_data('RSAFS')
        retail_ann = fetch_annual_growth('RSAFS')
        pce_ann = fetch_annual_growth('PCE')
        pcec96_ann = fetch_annual_growth('PCEC96')
        sentiment = fetch_peak_reversal('UMCSENT', 1)
        dgorder_yoy = fetch_yoy_data('DGORDER')
        dgorder_ann = fetch_annual_growth('DGORDER')
        pnfi = fetch_annual_growth('PNFI')
        prfi = fetch_annual_growth('PRFI')
        gpdic1_ann = fetch_annual_growth('GPDIC1')
        gpdic1_saar = fetch_saar_data('GPDIC1')
        pmi = fetch_trend_data('NAPM', 180)
        cpi = fetch_annual_growth('CPIAUCSL')
        t10y2y = fetch_trend_data('T10Y2Y')
        govt = fetch_annual_growth('SLEXND')
        isratio = fetch_peak_reversal('ISRATIO', 1)
        dr_con = fetch_annual_growth('DRCLACBS')
        dr_bus = fetch_annual_growth('DRBLACBS')

        # ---------------- 邏輯運算與計分 ----------------
        scores = {"recovery": 0, "growth": 0, "boom_warning": 0, "recession": 0, "bottom": 0}

        if fed and (fed['trend_down'] or fed['latest'] < 2.5): scores["recovery"] += 1
        if icsa_peak and icsa_peak['pct_from_min'] < 5.0: scores["recovery"] += 1
        if retail_yoy and retail_yoy['trend_rebound']: scores["recovery"] += 1
        if dgorder_yoy and (dgorder_yoy['trend_rebound'] or dgorder_yoy['yoy_now']>0): scores["recovery"] += 1

        if payems and payems['yoy'] > 1.0: scores["growth"] += 1
        if pnfi and pnfi['yoy'] > 2.0: scores["growth"] += 1
        if prfi and prfi['yoy'] > 2.0: scores["growth"] += 1
        if cpi and 1.5 <= cpi['yoy'] <= 4.0: scores["growth"] += 1

        if t10y2y and t10y2y['latest'] < 0: scores["boom_warning"] += 1
        if icsa_peak and icsa_peak['pct_from_min'] > 15.0: scores["boom_warning"] += 1
        if retail_ann and pce_ann and retail_ann['yoy'] < pce_ann['yoy'] and retail_ann['yoy'] < 2.0: scores["boom_warning"] += 1
        if sentiment and sentiment['pct_from_max'] < -10.0: scores["boom_warning"] += 1
        if dgorder_ann and dgorder_ann['yoy'] < 0: scores["boom_warning"] += 1
        if govt and govt['yoy'] < 0: scores["boom_warning"] += 1
        if isratio and isratio.get('min') and isratio['min'] > 0 and isratio['latest'] > isratio['min'] * 1.05: scores["boom_warning"] += 1 
        if dr_con and dr_bus and dr_con['yoy'] > 10.0 and dr_bus['yoy'] > 10.0: scores["boom_warning"] += 1

        if pcec96_ann and pcec96_ann['yoy'] < 1.0: scores["recession"] += 1
        if gpdic1_ann and gpdic1_ann['yoy'] < 0: scores["recession"] += 1

        if gpdic1_saar and gpdic1_saar['rebounding']: scores["bottom"] += 1
        if retail_yoy and retail_yoy['trend_rebound']: scores["bottom"] += 1
        if pmi and pmi['latest'] > 42.0 and not pmi['trend_down']: scores["bottom"] += 1

        # ---------------- 階層式決策樹 ----------------
        if scores["recession"] >= 1:
            if scores["bottom"] >= 2:
                verdict = "🥶 衰退期 (末端) - 底部反轉曙光已現"
                strategy = "絕佳入市時機！執行 U 型扣款分批大買股票，持有長債享受降息紅利，高收益債亦可搶跌深反彈。"
            else:
                verdict = "🥶 衰退期 (主跌段) - 景氣嚴冬"
                strategy = "重壓無風險長天期公債與美元避險，股市僅限小額定期定額，切勿輕易 All-in 猜底。"
        elif scores["boom_warning"] >= 4 or (t10y2y and t10y2y['latest'] < 0 and scores['boom_warning'] >= 2):
            verdict = "🔥 榮景期 (末端) - 衰退轉折危機"
            strategy = "午夜12點即將到來！迅速將持股降至 30%~50%，重壓長天期公債準備迎接衰退，全面避開高收益債與原物料。"
        elif scores["growth"] >= 3:
            verdict = "📈 穩定成長期"
            strategy = "維持高持股部位，享受時間複利。避開面臨跌價風險的無風險公債，保守者可持有高收益債。"
        elif scores["recovery"] >= 3:
            verdict = "🌱 景氣復甦期"
            strategy = "股市被低估，勇敢錢進風險資產，適度放大槓桿！無風險債券準備獲利了結轉出。"
        elif scores["boom_warning"] >= 1:
            verdict = "🥂 榮景期 (高檔熱絡)"
            strategy = "享受最後的末升段，維持 70% 持股，但不可失去戒心，隨時觀察警訊變化。"
        else:
            verdict = "🌀 週期過渡期 (多空交雜)"
            strategy = "目前多空數據交雜，可能正處於階段轉換的過渡期。建議維持股債平衡配置，靜待更明確的信號。"

        # 準備前端展示用數據
        raw_data = {
            "FEDFUNDS (聯邦基準利率)": f"{fed['latest']}%" if fed else "N/A",
            "ICSA (初領失業金反彈)": f"{icsa_peak['pct_from_min']}%" if icsa_peak else "N/A",
            "PAYEMS (非農就業 YoY)": f"{payems['yoy']}%" if payems else "N/A",
            "RSAFS (零售銷售 YoY)": f"{retail_ann['yoy']}%" if retail_ann else "N/A",
            "PCE (個人消費 YoY)": f"{pce_ann['yoy']}%" if pce_ann else "N/A",
            "PCEC96 (實質消費 YoY)": f"{pcec96_ann['yoy']}%" if pcec96_ann else "N/A",
            "UMCSENT (信心高點滑落)": f"{sentiment['pct_from_max']}%" if sentiment else "N/A",
            "DGORDER (耐久財訂單 YoY)": f"{dgorder_ann['yoy']}%" if dgorder_ann else "N/A",
            "PNFI (民間固定投資 YoY)": f"{pnfi['yoy']}%" if pnfi else "N/A",
            "PRFI (私人住宅投資 YoY)": f"{prfi['yoy']}%" if prfi else "N/A",
            "GPDIC1 (實質民間投資 YoY)": f"{gpdic1_ann['yoy']}%" if gpdic1_ann else "N/A",
            "GPDIC1 Saar (投資季增年率)": f"{gpdic1_saar['saar_now']}%" if gpdic1_saar else "N/A",
            "NAPM (採購經理人 PMI)": f"{pmi['latest']}" if pmi else "N/A",
            "CPIAUCSL (通貨膨脹 YoY)": f"{cpi['yoy']}%" if cpi else "N/A",
            "T10Y2Y (10減2年公債利差)": f"{t10y2y['latest']}%" if t10y2y else "N/A",
            "SLEXND (地方政府支出 YoY)": f"{govt['yoy']}%" if govt else "N/A",
            "ISRATIO (庫存銷售比)": f"{isratio['latest']}" if isratio else "N/A",
            "DRCLACBS (消費違約 YoY)": f"{dr_con['yoy']}%" if dr_con else "N/A",
            "DRBLACBS (企業違約 YoY)": f"{dr_bus['yoy']}%" if dr_bus else "N/A",
        }

        return {
            "timestamp": now.strftime("%Y-%m-%d %H:%M"),
            "verdict": verdict,
            "strategy": strategy,
            "scores": scores,
            "raw_data": raw_data
        }
    except Exception as e:
        return {"error": str(e)}
