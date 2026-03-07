from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from .utils import get_comprehensive_data
from .models import EconomicRecord
import logging

logger = logging.getLogger(__name__)

def home(request):
    try:
        # 嘗試取得歷史日期清單供首頁下拉選單使用
        history_dates = EconomicRecord.objects.values_list('date', flat=True).order_by('-date')
        dates_list = list(history_dates)
    except Exception as e:
        # 【防呆機制】如果資料庫還沒建好，攔截錯誤，回傳空清單，保證首頁不崩潰
        print(f"資料庫尚未建立或讀取失敗: {e}")
        dates_list = []
        
    return render(request, 'analyzer/home.html', {'history_dates': dates_list})


def economic_dashboard(request):
    api_key = "31c9ce02b76b2d4e4942671c7f86624a"
    selected_date = request.GET.get('date')
    force_refresh = request.GET.get('refresh') == 'true'
    
    results = None

    # 1. 如果使用者選擇了歷史日期，且沒有強制更新
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
            print(f"無法讀取該日歷史紀錄，轉為即時爬蟲: {e}")

    # 2. 如果找不到紀錄、沒有選擇日期、或是強制要求最新資料
    if not results:
        results = get_comprehensive_data(api_key)
        
        # 爬蟲成功沒有報錯的話，嘗試存入資料庫
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
                # 【防呆機制】存不進去就算了，直接顯示最新運算結果，絕不崩潰
                print(f"資料庫寫入失敗: {e}")
                results['record_date'] = str(timezone.localtime().date())

    # 3. 處理 JSON 輸出
    if request.GET.get('export') == 'json':
        return JsonResponse(results, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 4})
        
    # 4. 正常網頁渲染
    return render(request, 'analyzer/dashboard.html', {'results': results})
