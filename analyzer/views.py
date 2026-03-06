from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from .utils import get_comprehensive_data
from .models import EconomicRecord
import logging

logger = logging.getLogger(__name__)

def home(request):
    # 取得歷史日期清單供首頁下拉選單使用
    history_dates = EconomicRecord.objects.values_list('date', flat=True).order_by('-date')
    return render(request, 'analyzer/home.html', {'history_dates': history_dates})

def economic_dashboard(request):
    api_key = "31c9ce02b76b2d4e4942671c7f86624a"
    selected_date = request.GET.get('date')
    force_refresh = request.GET.get('refresh') == 'true'
    
    if selected_date and not force_refresh:
        # 從資料庫撈取歷史紀錄
        try:
            record = EconomicRecord.objects.get(date=selected_date)
            results = {
                "timestamp": record.created_at.strftime('%Y-%m-%d %H:%M:%S') + " (歷史快取)",
                "verdict": record.verdict,
                "strategy": record.strategy,
                "scores": record.scores,
                "raw_data": record.raw_data,
                "details": record.details,
                "record_date": str(record.date)
            }
        except EconomicRecord.DoesNotExist:
            results = get_comprehensive_data(api_key)
    else:
        # 執行最新爬蟲
        results = get_comprehensive_data(api_key)
        if "error" not in results:
            # 存入資料庫，一天存一筆 (update_or_create)
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

    if request.GET.get('export') == 'json':
        return JsonResponse(results, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 4})
        
    return render(request, 'analyzer/dashboard.html', {'results': results})
