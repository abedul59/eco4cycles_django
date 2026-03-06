
# Create your models here.
from django.db import models

class CycleRecord(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="分析時間")
    stage_3y = models.IntegerField(null=True, blank=True, verbose_name="3年基準判定階段")
    stage_1y = models.IntegerField(null=True, blank=True, verbose_name="1年基準判定階段")
    stage_6m = models.IntegerField(null=True, blank=True, verbose_name="半年基準判定階段")
    stage_3m = models.IntegerField(null=True, blank=True, verbose_name="3個月基準判定階段")
    raw_data = models.JSONField(verbose_name="完整原始數據與趨勢")

    class Meta:
        ordering = ['-created_at'] # 預設按時間倒序排列

    def __str__(self):
        return f"{self.created_at.strftime('%Y-%m-%d')} - 半年基準階段: {self.stage_6m}"

from django.db import models

class EconomicRecord(models.Model):
    date = models.DateField(unique=True, verbose_name="記錄日期")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="抓取時間")
    verdict = models.CharField(max_length=200, verbose_name="週期判定")
    strategy = models.TextField(verbose_name="投資策略")
    raw_data = models.JSONField(verbose_name="原始數據")
    scores = models.JSONField(verbose_name="分數統計")
    details = models.JSONField(verbose_name="觸發細節敘述", default=dict)

    def __str__(self):
        return str(self.date)
    
    class Meta:
        ordering = ['-date'] # 依照日期新到舊排序
