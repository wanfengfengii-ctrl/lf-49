from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .validators import validate_non_negative, validate_year


class Weir(models.Model):
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='鱼梁编号',
        help_text='鱼梁唯一编号，不能重复'
    )
    name = models.CharField(max_length=100, verbose_name='鱼梁名称')
    location = models.CharField(max_length=200, verbose_name='所在位置')
    build_year = models.IntegerField(
        validators=[validate_year],
        verbose_name='建造年代',
        null=True,
        blank=True
    )
    gate_count = models.IntegerField(
        validators=[validate_non_negative],
        default=1,
        verbose_name='闸口数量'
    )
    structure_desc = models.TextField(
        verbose_name='结构描述',
        blank=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )

    class Meta:
        verbose_name = '鱼梁档案'
        verbose_name_plural = '鱼梁档案'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'

    def clean(self):
        self.code = self.code.strip().upper()
        super().clean()


class WaterLevel(models.Model):
    WEATHER_CHOICES = [
        ('晴', '晴'),
        ('多云', '多云'),
        ('阴', '阴'),
        ('小雨', '小雨'),
        ('中雨', '中雨'),
        ('大雨', '大雨'),
        ('暴雨', '暴雨'),
        ('雪', '雪'),
        ('雾', '雾'),
    ]

    weir = models.ForeignKey(
        Weir,
        on_delete=models.CASCADE,
        related_name='water_levels',
        verbose_name='所属鱼梁'
    )
    record_date = models.DateField(verbose_name='记录日期')
    water_level = models.FloatField(
        validators=[validate_non_negative],
        verbose_name='水位(米)',
        help_text='水位高度，不能为负数'
    )
    flow_rate = models.FloatField(
        validators=[validate_non_negative],
        verbose_name='流速(m/s)',
        help_text='水流速度，不能为负数'
    )
    weather = models.CharField(
        max_length=20,
        choices=WEATHER_CHOICES,
        verbose_name='天气状况'
    )
    notes = models.TextField(verbose_name='备注', blank=True)
    is_primary = models.BooleanField(
        default=True,
        verbose_name='是否主记录',
        help_text='同一鱼梁同一天只能有一条主记录'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )

    class Meta:
        verbose_name = '水位记录'
        verbose_name_plural = '水位记录'
        ordering = ['-record_date', 'weir__code']
        constraints = [
            models.UniqueConstraint(
                fields=['weir', 'record_date', 'is_primary'],
                condition=models.Q(is_primary=True),
                name='unique_primary_water_level_per_day'
            )
        ]
        indexes = [
            models.Index(fields=['weir', 'record_date']),
        ]

    def __str__(self):
        return f'{self.weir.code} - {self.record_date} - {self.water_level}m'

    def clean(self):
        super().clean()
        if self.is_primary:
            existing = WaterLevel.objects.filter(
                weir=self.weir,
                record_date=self.record_date,
                is_primary=True
            )
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError({
                    'is_primary': _('该鱼梁在 %(date)s 已有一条主水位记录'),
                }, params={'date': self.record_date})


class GateStatus(models.Model):
    STATUS_CHOICES = [
        ('open', '开启'),
        ('closed', '关闭'),
    ]

    weir = models.ForeignKey(
        Weir,
        on_delete=models.CASCADE,
        related_name='gate_statuses',
        verbose_name='所属鱼梁'
    )
    gate_number = models.CharField(
        max_length=20,
        verbose_name='闸口编号'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        verbose_name='状态'
    )
    change_time = models.DateTimeField(
        default=timezone.now,
        verbose_name='变更时间'
    )
    reason = models.TextField(
        verbose_name='变更原因',
        blank=True
    )
    operator = models.CharField(
        max_length=50,
        verbose_name='操作人',
        blank=True
    )

    class Meta:
        verbose_name = '闸口状态'
        verbose_name_plural = '闸口状态'
        ordering = ['-change_time', 'weir__code', 'gate_number']
        indexes = [
            models.Index(fields=['weir', 'change_time']),
        ]

    def __str__(self):
        status_display = dict(self.STATUS_CHOICES)[self.status]
        return f'{self.weir.code} - {self.gate_number} - {status_display}'


class HarvestRecord(models.Model):
    weir = models.ForeignKey(
        Weir,
        on_delete=models.CASCADE,
        related_name='harvest_records',
        verbose_name='所属鱼梁'
    )
    record_date = models.DateField(verbose_name='记录日期')
    fish_species = models.CharField(
        max_length=50,
        verbose_name='鱼种'
    )
    weight = models.FloatField(
        validators=[validate_non_negative],
        verbose_name='重量(公斤)',
        help_text='捕获重量，不能为负数'
    )
    quantity = models.IntegerField(
        validators=[validate_non_negative],
        default=0,
        verbose_name='数量',
        help_text='捕获数量，不能为负数'
    )
    recorder = models.CharField(
        max_length=50,
        verbose_name='记录人',
        blank=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )

    class Meta:
        verbose_name = '收获记录'
        verbose_name_plural = '收获记录'
        ordering = ['-record_date', 'weir__code']
        indexes = [
            models.Index(fields=['weir', 'record_date']),
        ]

    def __str__(self):
        return f'{self.weir.code} - {self.record_date} - {self.fish_species} {self.weight}kg'


class FishSchool(models.Model):
    DIRECTION_CHOICES = [
        ('upstream', '逆流而上'),
        ('downstream', '顺流而下'),
    ]

    weir = models.ForeignKey(
        Weir,
        on_delete=models.CASCADE,
        related_name='fish_schools',
        verbose_name='所属鱼梁'
    )
    record_date = models.DateField(verbose_name='记录日期')
    observe_time = models.TimeField(verbose_name='观测时间')
    fish_type = models.CharField(
        max_length=50,
        verbose_name='鱼群种类'
    )
    estimated_count = models.IntegerField(
        validators=[validate_non_negative],
        verbose_name='预估数量'
    )
    direction = models.CharField(
        max_length=20,
        choices=DIRECTION_CHOICES,
        verbose_name='游动方向'
    )
    notes = models.TextField(verbose_name='备注', blank=True)

    class Meta:
        verbose_name = '鱼群记录'
        verbose_name_plural = '鱼群记录'
        ordering = ['-record_date', '-observe_time', 'weir__code']

    def __str__(self):
        return f'{self.weir.code} - {self.record_date} {self.observe_time} - {self.fish_type}'


class HarvestEstimate(models.Model):
    weir = models.ForeignKey(
        Weir,
        on_delete=models.CASCADE,
        related_name='harvest_estimates',
        verbose_name='所属鱼梁'
    )
    estimate_date = models.DateField(verbose_name='估算日期')
    estimated_weight = models.FloatField(
        validators=[validate_non_negative],
        verbose_name='估算重量(公斤)',
        default=0
    )
    gate_strategy = models.CharField(
        max_length=200,
        verbose_name='闸口策略组合',
        blank=True
    )
    water_level = models.FloatField(
        verbose_name='当日水位',
        null=True,
        blank=True
    )
    has_water_data = models.BooleanField(
        default=False,
        verbose_name='是否有水位数据'
    )
    actual_weight = models.FloatField(
        validators=[validate_non_negative],
        verbose_name='实际重量(公斤)',
        default=0
    )
    accuracy = models.FloatField(
        verbose_name='估算准确率(%)',
        null=True,
        blank=True
    )
    calculated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='计算时间'
    )

    class Meta:
        verbose_name = '收获估算'
        verbose_name_plural = '收获估算'
        ordering = ['-estimate_date', 'weir__code']
        constraints = [
            models.UniqueConstraint(
                fields=['weir', 'estimate_date'],
                name='unique_estimate_per_day'
            )
        ]
        indexes = [
            models.Index(fields=['weir', 'estimate_date']),
        ]

    def __str__(self):
        return f'{self.weir.code} - {self.estimate_date} - 估算{self.estimated_weight}kg'

    def calculate_accuracy(self):
        if self.estimated_weight > 0 and self.actual_weight > 0:
            self.accuracy = round(
                (1 - abs(self.estimated_weight - self.actual_weight) / self.actual_weight) * 100,
                2
            )
        else:
            self.accuracy = None
        return self.accuracy

    def save(self, *args, **kwargs):
        self.calculate_accuracy()
        super().save(*args, **kwargs)
