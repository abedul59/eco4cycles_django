from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from .utils import get_comprehensive_data
from .models import EconomicRecord
import logging

logger = logging.getLogger(__name__)

def home(request):
    try:
        history_dates = EconomicRecord.objects.values_list('date', flat=True).order_by('-date')
        dates_list = list(history_dates)
        db_status = "ok"
    except Exception as e:
        # 將錯誤抓出來，傳給前端顯示
        dates_list = []
        db_status = str(e)
        
    return render(request, 'analyzer/home.html', {
        'history_dates': dates_list, 
        'db_status': db_status
    })


def economic_dashboard(request):
    api_key = "31c9ce02b76b2d4e4942671c7f86624a"
    selected_date = request.GET.get('date')
    force_refresh = request.GET.get('refresh') == 'true'
    
    results = None

    # 1. 嘗試讀取歷史紀錄
    if selected_date and not force_refresh:
        try:
            record = EconomicRecord.objects.get(date=selected_date)
            results = {
                "timestamp": record.created_at.strftime('%Y-%m-%d %H:%M:%S') + " (歷史紀錄快取)",
                "verdict": record.verdict,
                "strategy": record.strategy,
                "scores": record.scores,
                "raw_data": record.raw_data,
                "details": record.details,
                "record_date": str(record.date)
            }
        except Exception as e:
            print(f"無法讀取該日歷史紀錄: {e}")

    # 2. 如果沒有歷史紀錄，執行即時爬蟲
    if not results:
        results = get_comprehensive_data(api_key)
        
        if "error" not in results:
            try:
                today = timezone.localtime().date()
                EconomicRecord.objects.update_or_create(
                    date=today,
                    defaults={
                        'verdict': results['verdict'],
                        'strategy': results['strategy'],
                        'raw_data': results['raw_data'],
                        'scores': results['scores'],
                        'details': results['details']
                    }
                )
                results['record_date'] = str(today)
            except Exception as e:
                # 寫入失敗時，把錯誤存進 results 傳給網頁
                results['db_error'] = str(e)
                results['record_date'] = str(timezone.localtime().date())

    # 3. JSON 輸出
    if request.GET.get('export') == 'json':
        return JsonResponse(results, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 4})
        
    # 4. 網頁渲染
    return render(request, 'analyzer/dashboard.html', {'results': results})
