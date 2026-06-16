from django.contrib import admin
from .models import Weir, WaterLevel, GateStatus, HarvestRecord, FishSchool, HarvestEstimate


class WaterLevelInline(admin.TabularInline):
    model = WaterLevel
    extra = 0
    fields = ('record_date', 'water_level', 'flow_rate', 'weather', 'is_primary')
    readonly_fields = ('created_at',)


class GateStatusInline(admin.TabularInline):
    model = GateStatus
    extra = 0
    fields = ('gate_number', 'status', 'change_time', 'operator')


class HarvestRecordInline(admin.TabularInline):
    model = HarvestRecord
    extra = 0
    fields = ('record_date', 'fish_species', 'weight', 'quantity', 'recorder')


class HarvestEstimateInline(admin.TabularInline):
    model = HarvestEstimate
    extra = 0
    fields = ('estimate_date', 'estimated_weight', 'actual_weight', 'accuracy', 'gate_strategy', 'has_water_data')
    readonly_fields = ('calculated_at',)


@admin.register(Weir)
class WeirAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'location', 'build_year', 'gate_count', 'created_at')
    search_fields = ('code', 'name', 'location')
    list_filter = ('build_year', 'gate_count')
    ordering = ('code',)
    inlines = [WaterLevelInline, GateStatusInline, HarvestRecordInline, HarvestEstimateInline]
    fieldsets = (
        ('基本信息', {
            'fields': ('code', 'name', 'location', 'build_year', 'gate_count')
        }),
        ('详细描述', {
            'fields': ('structure_desc',),
            'classes': ('collapse',)
        }),
    )


@admin.register(WaterLevel)
class WaterLevelAdmin(admin.ModelAdmin):
    list_display = ('weir', 'record_date', 'water_level', 'flow_rate', 'weather', 'is_primary', 'created_at')
    list_filter = ('weir', 'record_date', 'weather', 'is_primary')
    search_fields = ('weir__code', 'weir__name', 'weather')
    date_hierarchy = 'record_date'
    ordering = ('-record_date', 'weir__code')
    fieldsets = (
        ('基本信息', {
            'fields': ('weir', 'record_date', 'is_primary')
        }),
        ('水文数据', {
            'fields': ('water_level', 'flow_rate', 'weather')
        }),
        ('备注', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(GateStatus)
class GateStatusAdmin(admin.ModelAdmin):
    list_display = ('weir', 'gate_number', 'status', 'change_time', 'operator')
    list_filter = ('weir', 'status', 'change_time')
    search_fields = ('weir__code', 'gate_number', 'operator')
    date_hierarchy = 'change_time'
    ordering = ('-change_time', 'weir__code', 'gate_number')
    fieldsets = (
        ('基本信息', {
            'fields': ('weir', 'gate_number', 'status', 'change_time')
        }),
        ('详细信息', {
            'fields': ('reason', 'operator')
        }),
    )


@admin.register(HarvestRecord)
class HarvestRecordAdmin(admin.ModelAdmin):
    list_display = ('weir', 'record_date', 'fish_species', 'weight', 'quantity', 'recorder', 'created_at')
    list_filter = ('weir', 'record_date', 'fish_species')
    search_fields = ('weir__code', 'fish_species', 'recorder')
    date_hierarchy = 'record_date'
    ordering = ('-record_date', 'weir__code')
    fieldsets = (
        ('基本信息', {
            'fields': ('weir', 'record_date', 'fish_species')
        }),
        ('收获数据', {
            'fields': ('weight', 'quantity')
        }),
        ('记录信息', {
            'fields': ('recorder',)
        }),
    )


@admin.register(FishSchool)
class FishSchoolAdmin(admin.ModelAdmin):
    list_display = ('weir', 'record_date', 'observe_time', 'fish_type', 'estimated_count', 'direction')
    list_filter = ('weir', 'record_date', 'fish_type', 'direction')
    search_fields = ('weir__code', 'fish_type')
    date_hierarchy = 'record_date'
    ordering = ('-record_date', '-observe_time', 'weir__code')


@admin.register(HarvestEstimate)
class HarvestEstimateAdmin(admin.ModelAdmin):
    list_display = ('weir', 'estimate_date', 'estimated_weight', 'actual_weight', 'accuracy', 'has_water_data', 'gate_strategy', 'calculated_at')
    list_filter = ('weir', 'estimate_date', 'has_water_data', 'gate_strategy')
    search_fields = ('weir__code', 'gate_strategy')
    date_hierarchy = 'estimate_date'
    ordering = ('-estimate_date', 'weir__code')
    readonly_fields = ('calculated_at', 'accuracy')
    fieldsets = (
        ('基本信息', {
            'fields': ('weir', 'estimate_date')
        }),
        ('估算数据', {
            'fields': ('estimated_weight', 'actual_weight', 'accuracy', 'gate_strategy')
        }),
        ('数据状态', {
            'fields': ('water_level', 'has_water_data', 'calculated_at')
        }),
    )
