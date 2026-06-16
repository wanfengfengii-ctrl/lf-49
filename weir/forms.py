from django import forms
from .models import Weir, WaterLevel, GateStatus, HarvestRecord, FishSchool


class WeirForm(forms.ModelForm):
    class Meta:
        model = Weir
        fields = ['code', 'name', 'location', 'build_year', 'gate_count', 'structure_desc']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '如：YL-001'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入鱼梁名称'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入所在位置'}),
            'build_year': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '如：1950'}),
            'gate_count': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'structure_desc': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': '请输入结构描述'}),
        }
        labels = {
            'code': '鱼梁编号',
            'name': '鱼梁名称',
            'location': '所在位置',
            'build_year': '建造年代',
            'gate_count': '闸口数量',
            'structure_desc': '结构描述',
        }


class WaterLevelForm(forms.ModelForm):
    class Meta:
        model = WaterLevel
        fields = ['weir', 'record_date', 'water_level', 'flow_rate', 'weather', 'is_primary', 'notes']
        widgets = {
            'weir': forms.Select(attrs={'class': 'form-control'}),
            'record_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'water_level': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'flow_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'weather': forms.Select(attrs={'class': 'form-control'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'weir': '所属鱼梁',
            'record_date': '记录日期',
            'water_level': '水位(米)',
            'flow_rate': '流速(m/s)',
            'weather': '天气状况',
            'is_primary': '是否为主记录',
            'notes': '备注',
        }
        help_texts = {
            'water_level': '水位高度，不能为负数',
            'flow_rate': '水流速度，不能为负数',
            'is_primary': '同一鱼梁同一天只能有一条主记录',
        }


class GateStatusForm(forms.ModelForm):
    class Meta:
        model = GateStatus
        fields = ['weir', 'gate_number', 'status', 'change_time', 'reason', 'operator']
        widgets = {
            'weir': forms.Select(attrs={'class': 'form-control'}),
            'gate_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '如：G-1'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'change_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'operator': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'weir': '所属鱼梁',
            'gate_number': '闸口编号',
            'status': '状态',
            'change_time': '变更时间',
            'reason': '变更原因',
            'operator': '操作人',
        }


class HarvestRecordForm(forms.ModelForm):
    class Meta:
        model = HarvestRecord
        fields = ['weir', 'record_date', 'fish_species', 'weight', 'quantity', 'recorder']
        widgets = {
            'weir': forms.Select(attrs={'class': 'form-control'}),
            'record_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fish_species': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '如：鲤鱼'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'recorder': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'weir': '所属鱼梁',
            'record_date': '记录日期',
            'fish_species': '鱼种',
            'weight': '重量(公斤)',
            'quantity': '数量',
            'recorder': '记录人',
        }
        help_texts = {
            'weight': '捕获重量，不能为负数',
            'quantity': '捕获数量，不能为负数',
        }


class FishSchoolForm(forms.ModelForm):
    class Meta:
        model = FishSchool
        fields = ['weir', 'record_date', 'observe_time', 'fish_type', 'estimated_count', 'direction', 'notes']
        widgets = {
            'weir': forms.Select(attrs={'class': 'form-control'}),
            'record_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observe_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'fish_type': forms.TextInput(attrs={'class': 'form-control'}),
            'estimated_count': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'direction': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'weir': '所属鱼梁',
            'record_date': '记录日期',
            'observe_time': '观测时间',
            'fish_type': '鱼群种类',
            'estimated_count': '预估数量',
            'direction': '游动方向',
            'notes': '备注',
        }


class ReportFilterForm(forms.Form):
    weir = forms.ModelChoiceField(
        queryset=Weir.objects.all(),
        required=False,
        label='选择鱼梁',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    start_date = forms.DateField(
        required=False,
        label='开始日期',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    end_date = forms.DateField(
        required=False,
        label='结束日期',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )


SEASON_CHOICES = [
    ('spring', '春季（3-5月）'),
    ('summer', '夏季（6-8月）'),
    ('autumn', '秋季（9-11月）'),
    ('winter', '冬季（12-2月）'),
]

MONTH_CHOICES = [
    (1, '1月'), (2, '2月'), (3, '3月'), (4, '4月'),
    (5, '5月'), (6, '6月'), (7, '7月'), (8, '8月'),
    (9, '9月'), (10, '10月'), (11, '11月'), (12, '12月'),
]

WEATHER_CHOICES = [
    ('晴', '晴'), ('多云', '多云'), ('阴', '阴'),
    ('小雨', '小雨'), ('中雨', '中雨'), ('大雨', '大雨'),
    ('暴雨', '暴雨'), ('雪', '雪'), ('雾', '雾'),
]

GATE_STATUS_CHOICES = [
    ('open', '开启'),
    ('closed', '关闭'),
]


class ComprehensiveFilterForm(forms.Form):
    weir = forms.ModelChoiceField(
        queryset=Weir.objects.all(),
        required=False,
        label='选择鱼梁',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    season = forms.MultipleChoiceField(
        choices=SEASON_CHOICES,
        required=False,
        label='季节',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'checkbox-inline'})
    )
    months = forms.MultipleChoiceField(
        choices=MONTH_CHOICES,
        required=False,
        label='月份',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'checkbox-inline'})
    )
    start_date = forms.DateField(
        required=False,
        label='开始日期',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    end_date = forms.DateField(
        required=False,
        label='结束日期',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    water_level_min = forms.FloatField(
        required=False,
        label='最低水位(米)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'})
    )
    water_level_max = forms.FloatField(
        required=False,
        label='最高水位(米)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'})
    )
    flow_rate_min = forms.FloatField(
        required=False,
        label='最低流速(m/s)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'})
    )
    flow_rate_max = forms.FloatField(
        required=False,
        label='最高流速(m/s)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'})
    )
    weather = forms.MultipleChoiceField(
        choices=WEATHER_CHOICES,
        required=False,
        label='天气状况',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'checkbox-inline'})
    )
    gate_strategy = forms.CharField(
        required=False,
        label='闸口策略（如：G-1开,G-2关）',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '可选，精确匹配闸口策略组合'})
    )
    gate_status = forms.ChoiceField(
        choices=[('', '全部')] + GATE_STATUS_CHOICES,
        required=False,
        label='闸口状态',
        widget=forms.Select(attrs={'class': 'form-control'})
    )


SIMULATION_MODE_CHOICES = [
    ('single', '单策略模拟'),
    ('multi', '多策略对比'),
    ('reconstruct', '历史作业复原'),
]


class FishMigrationFilterForm(forms.Form):
    weir = forms.ModelChoiceField(
        queryset=Weir.objects.all(),
        required=False,
        label='选择鱼梁',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    season = forms.MultipleChoiceField(
        choices=SEASON_CHOICES,
        required=False,
        label='季节',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'checkbox-inline'})
    )
    months = forms.MultipleChoiceField(
        choices=MONTH_CHOICES,
        required=False,
        label='月份',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'checkbox-inline'})
    )
    start_date = forms.DateField(
        required=False,
        label='开始日期',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    end_date = forms.DateField(
        required=False,
        label='结束日期',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    water_level_min = forms.FloatField(
        required=False,
        label='最低水位(米)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'})
    )
    water_level_max = forms.FloatField(
        required=False,
        label='最高水位(米)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'})
    )
    flow_rate_min = forms.FloatField(
        required=False,
        label='最低流速(m/s)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'})
    )
    flow_rate_max = forms.FloatField(
        required=False,
        label='最高流速(m/s)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'})
    )
    weather = forms.MultipleChoiceField(
        choices=WEATHER_CHOICES,
        required=False,
        label='天气状况',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'checkbox-inline'})
    )
    fish_species = forms.MultipleChoiceField(
        choices=[],
        required=False,
        label='鱼种',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'checkbox-inline'})
    )
    gate_status = forms.MultipleChoiceField(
        choices=GATE_STATUS_CHOICES,
        required=False,
        label='闸口状态',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'checkbox-inline'})
    )
    gate_strategy = forms.CharField(
        required=False,
        label='闸口策略（如：G-1开,G-2关）',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '可选，精确匹配闸口策略组合'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .services.fish_migration_analyzer import get_available_fish_species
        species_list = get_available_fish_species()
        self.fields['fish_species'].choices = [(s, s) for s in species_list]


class SimulationForm(forms.Form):
    weir = forms.ModelChoiceField(
        queryset=Weir.objects.all(),
        required=True,
        label='选择鱼梁',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    simulation_mode = forms.ChoiceField(
        choices=SIMULATION_MODE_CHOICES,
        required=True,
        label='模拟模式',
        initial='single',
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'simulation_mode'})
    )
    simulation_date = forms.DateField(
        required=True,
        label='模拟日期',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    water_level = forms.FloatField(
        required=True,
        label='模拟水位(米)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'})
    )
    flow_rate = forms.FloatField(
        required=True,
        label='模拟流速(m/s)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'})
    )
    weather = forms.ChoiceField(
        choices=WEATHER_CHOICES,
        required=True,
        label='天气状况',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    gate_config = forms.CharField(
        required=False,
        label='闸口配置（如：G-1开,G-2关）',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入闸口策略组合'})
    )
    historical_period = forms.ChoiceField(
        choices=[
            ('recent', '近年模式（近5年数据）'),
            ('traditional', '传统模式（1980-2000年）'),
            ('all', '全数据模式'),
        ],
        required=True,
        label='历史参照模式',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
