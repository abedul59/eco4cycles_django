from django.shortcuts import render
from django.http import JsonResponse
from .utils import get_comprehensive_data
import logging

logger = logging.getLogger(__name__)

def home(request):
    return render(request, 'analyzer/home.html')

def economic_dashboard(request):
    api_key = "31c9ce02b76b2d4e4942671c7f86624a"
    
    # 呼叫完整版爬蟲引擎
    results = get_comprehensive_data(api_key)
    
    # 手機端或 API 若請求 JSON 格式
    if request.GET.get('export') == 'json':
        return JsonResponse(results, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 4})
        
    # 【修復 500 錯誤】: 加上 'analyzer/' 前綴
    return render(request, 'analyzer/dashboard.html', {'results': results})
