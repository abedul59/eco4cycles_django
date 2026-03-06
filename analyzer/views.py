from django.shortcuts import render, redirect
from django.contrib import messages
from .models import CycleRecord
from fredapi import Fred
import pandas as pd
from datetime import datetime, timedelta
import requests
import xml.etree.ElementTree as ET
import os


from django.shortcuts import render
from django.http import JsonResponse
from .utils import get_comprehensive_data

def economic_dashboard(request):
    api_key = "31c9ce02b76b2d4e4942671c7f86624a"
    results = get_comprehensive_data(api_key)
    
    if request.GET.get('export') == 'json':
        return JsonResponse(results, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 4})
        
    return render(request, 'dashboard.html', {'results': results})

# ================= 爬蟲與邏輯函式區 =================

def get_google_news_fallback(query):
    try:
        url = f"https://news.google.com/rss/search?q={query}+economic+data&hl=en-US&gl=US&ceid=US:en"
        response = requests.get(url, timeout=5)
        root = ET.fromstring(response.content)
        return [item.find('title').text for item in root.findall('./channel/item')[:3]]
    except Exception as e:
        return [f"無法獲取新聞: {str(e)}"]

def fetch_fred_data(fred, series_id, name, search_query):
    try:
        today = datetime.now()
        start_date = (today - timedelta(days=1200)).strftime('%Y-%m-%d')
        data = fred.get_series(series_id, observation_start=start_date)
        
        if data.empty or len(data) < 2:
            raise ValueError("資料筆數不足")
            
        data = data.dropna()
        latest_val = data.iloc[-1]
        
        target_dates = {
            "1個月": today - timedelta(days=30),
            "3個月": today - timedelta(days=90),
            "6個月": today - timedelta(days=180),
            "1年": today - timedelta(days=365),
            "2年": today - timedelta(days=730),
            "3年": today - timedelta(days=1095)
        }
        
        trends_info = {}
        for period, t_date in target_dates.items():
            if pd.Timestamp(t_date) < data.index[0]:
                closest_val = data.iloc[0] 
            else:
                idx = data.index.get_indexer([pd.Timestamp(t_date)], method='nearest')[0]
                closest_val = data.iloc[idx]
            
            change_pct = ((latest_val - closest_val) / closest_val) * 100
            
            if change_pct > 0.001:
                trend = "上升"
            elif change_pct < -0.001:
                trend = "下降"
            else:
                trend = "持平"
                
            trends_info[period] = {"trend": trend, "change": change_pct}
            
        return {
            "source": "FRED", 
            "latest": latest_val,
            "trends": trends_info
        }
        
    except Exception as e:
        news = get_google_news_fallback(search_query)
        return {"source": "GoogleNews", "news": news}

def evaluate_stage(all_trends):
    """計算並回傳各個時間維度所屬的階段"""
    periods = ["3年", "2年", "1年", "6個月", "3個月", "1個月"]
    stages_result = {}
    
    for period in periods:
        scores = {1: 0, 2: 0, 3: 0, 4: 0}

        def get_trend(indicator_name):
            data = all_trends.get(indicator_name)
            # 確保資料存在且包含 trends 字典
            if data and "trends" in data and period in data["trends"]:
                return data["trends"][period]["trend"]
            return "未知"

        m2 = get_trend("貨幣供給 (M2)")
        if m2 == "上升": scores[1] += 1; scores[2] += 1
        elif m2 == "下降": scores[3] += 1; scores[4] += 1

        stock = get_trend("股市表現 (S&P 500)")
        if stock == "上升": scores[1] += 1; scores[2] += 1; scores[4] += 1
        elif stock == "下降": scores[3] += 1

        rate = get_trend("短期利率 (3M T-Bill)")
        if rate == "下降": scores[1] += 1; scores[4] += 1
        elif rate == "上升": scores[2] += 1; scores[3] += 1

        cpi = get_trend("通貨膨脹 (CPI)")
        if cpi == "下降": scores[1] += 1; scores[4] += 1
        elif cpi == "上升": scores[2] += 1; scores[3] += 1

        profit = get_trend("企業獲利 (Profits)")
        if profit == "上升": scores[1] += 1; scores[2] += 1
        elif profit == "下降": scores[3] += 1; scores[4] += 1

        best_stage = max(scores, key=scores.get)
        stages_result[period] = best_stage
        
    return stages_result


# ================= Django 視圖 (View) =================

def home(request):
    # 優先從環境變數抓取 API Key，若無則使用寫死的預設值
    api_key = os.environ.get('FRED_API_KEY', '31c9ce02b76b2d4e4942671c7f86624a')
    
    if request.method == 'POST':
        try:
            fred = Fred(api_key=api_key)
            indicators = {
                "貨幣供給 (M2)": ("M2SL", "US M2 Money Supply"),
                "美元指數 (USD)": ("DTWEXAFEGS", "US Dollar Index"),
                "股市表現 (S&P 500)": ("SP500", "S&P 500 Stock Market"),
                "經濟成長 (Real GDP)": ("GDPC1", "US Real GDP Growth"),
                "企業獲利 (Profits)": ("CP", "US Corporate Profits"),
                "商品價格 (PPI)": ("PPIACO", "US Commodity Prices PPI"),
                "短期利率 (3M T-Bill)": ("TB3MS", "US 3 Month Treasury Bill Rate"),
                "長期利率 (10Y Yield)": ("GS10", "US 10 Year Treasury Yield"),
                "通貨膨脹 (CPI)": ("CPIAUCSL", "US CPI Inflation Rate")
            }
            
            results = {}
            for name, (series_id, query) in indicators.items():
                data = fetch_fred_data(fred, series_id, name, query)
                if data.get("source") == "FRED":
                    results[name] = {
                        "latest": float(data['latest']), 
                        "trends": data['trends']
                    }
                else:
                    results[name] = None

            # 取得各時段的判定階段 (會回傳一個字典，例如 {"3年": 1, "1年": 2, ...})
            stages = evaluate_stage(results)
            
            # 將資料寫入 Aiven (PostgreSQL) 資料庫
            CycleRecord.objects.create(
                stage_3y=stages.get("3年"),
                stage_1y=stages.get("1年"),
                stage_6m=stages.get("6個月"),
                stage_3m=stages.get("3個月"),
                raw_data=results
            )
            
            messages.success(request, '資料抓取與分析成功！已儲存至雲端資料庫。')
            return redirect('home')
            
        except Exception as e:
            messages.error(request, f'發生錯誤: {e}')

    # GET 請求時，從資料庫撈取最新一筆資料呈現在網頁上
    latest_record = CycleRecord.objects.first()
    return render(request, 'analyzer/home.html', {'record': latest_record})
