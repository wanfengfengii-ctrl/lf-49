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
