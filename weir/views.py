from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta
import json
from .models import Weir, WaterLevel, GateStatus, HarvestRecord, FishSchool, HarvestEstimate
from .forms import (
    WeirForm, WaterLevelForm, GateStatusForm, HarvestRecordForm,
    FishSchoolForm, ReportFilterForm, ComprehensiveFilterForm,
    SimulationForm, FishMigrationFilterForm
)
from .services.harvest_estimator import (
    get_monthly_trend, get_gate_strategy_comparison,
    recalculate_estimates, recalculate_all_estimates,
    get_comprehensive_analysis, get_seasonal_analysis,
    get_water_level_interval_analysis, get_flow_rate_analysis,
    get_weather_analysis, get_strategy_efficiency_comparison,
    get_monthly_comparison, simulate_harvest,
    simulate_multiple_strategies, get_typical_gate_configs,
    get_traditional_fishing_calendar, get_strategy_heatmap_data,
    get_multi_dimensional_comparison, get_comprehensive_strategy_analysis,
    reconstruct_historical_operation, get_historical_operation_patterns
)
from .services.fish_migration_analyzer import (
    get_comprehensive_migration_analysis,
    get_available_fish_species
)


def dashboard_index(request):
    total_weirs = Weir.objects.count()
    today = timezone.now().date()
    today_water_levels = WaterLevel.objects.filter(record_date=today).count()
    today_harvests = HarvestRecord.objects.filter(record_date=today).count()

    current_month = today.replace(day=1)
    next_month = (current_month + timedelta(days=32)).replace(day=1)
    monthly_harvest = HarvestRecord.objects.filter(
        record_date__gte=current_month,
        record_date__lt=next_month
    ).aggregate(total=Sum('weight'))['total'] or 0

    recent_water_levels = WaterLevel.objects.select_related('weir').order_by('-record_date', '-created_at')[:10]
    recent_harvests = HarvestRecord.objects.select_related('weir').order_by('-record_date', '-created_at')[:10]
    recent_gates = GateStatus.objects.select_related('weir').order_by('-change_time')[:10]

    last_30_days = today - timedelta(days=30)
    trend_data = get_monthly_trend(start_date=last_30_days)

    chart_labels = [d['month'] for d in trend_data]
    chart_estimated = [d['estimated'] for d in trend_data]
    chart_actual = [d['actual'] for d in trend_data]

    context = {
        'total_weirs': total_weirs,
        'today_water_levels': today_water_levels,
        'today_harvests': today_harvests,
        'monthly_harvest': round(monthly_harvest, 2),
        'recent_water_levels': recent_water_levels,
        'recent_harvests': recent_harvests,
        'recent_gates': recent_gates,
        'chart_labels': json.dumps(chart_labels),
        'chart_estimated': json.dumps(chart_estimated),
        'chart_actual': json.dumps(chart_actual),
    }
    return render(request, 'dashboard/index.html', context)


def weir_list(request):
    weirs = Weir.objects.all().annotate(
        water_level_count=Count('water_levels'),
        harvest_count=Count('harvest_records')
    )
    context = {'weirs': weirs}
    return render(request, 'weir/list.html', context)


def weir_create(request):
    if request.method == 'POST':
        form = WeirForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '鱼梁档案创建成功！')
            return redirect('weir_list')
    else:
        form = WeirForm()
    context = {'form': form, 'title': '新增鱼梁档案'}
    return render(request, 'weir/form.html', context)


def weir_detail(request, pk):
    weir = get_object_or_404(Weir, pk=pk)
    water_levels = weir.water_levels.all()[:20]
    harvests = weir.harvest_records.all()[:20]
    gate_statuses = weir.gate_statuses.all()[:20]
    estimates = weir.harvest_estimates.filter(has_water_data=True)[:20]

    timeline = []
    for wl in water_levels:
        timeline.append({
            'date': wl.record_date,
            'type': 'water',
            'data': wl,
        })
    for h in harvests:
        timeline.append({
            'date': h.record_date,
            'type': 'harvest',
            'data': h,
        })
    for g in gate_statuses:
        timeline.append({
            'date': g.change_time.date(),
            'type': 'gate',
            'data': g,
        })
    timeline.sort(key=lambda x: x['date'], reverse=True)

    context = {
        'weir': weir,
        'water_levels': water_levels,
        'harvests': harvests,
        'gate_statuses': gate_statuses,
        'estimates': estimates,
        'timeline': timeline[:30],
    }
    return render(request, 'weir/detail.html', context)


def weir_edit(request, pk):
    weir = get_object_or_404(Weir, pk=pk)
    if request.method == 'POST':
        form = WeirForm(request.POST, instance=weir)
        if form.is_valid():
            form.save()
            messages.success(request, '鱼梁档案更新成功！')
            return redirect('weir_detail', pk=pk)
    else:
        form = WeirForm(instance=weir)
    context = {'form': form, 'title': '编辑鱼梁档案', 'weir': weir}
    return render(request, 'weir/form.html', context)


def weir_delete(request, pk):
    weir = get_object_or_404(Weir, pk=pk)
    if request.method == 'POST':
        weir.delete()
        messages.success(request, '鱼梁档案删除成功！')
        return redirect('weir_list')
    context = {'weir': weir}
    return render(request, 'weir/delete.html', context)


def water_level_list(request):
    from django.db.models import Avg, Count
    form = ReportFilterForm(request.GET or None)
    water_levels = WaterLevel.objects.select_related('weir').all().order_by('-record_date', '-created_at')

    if form.is_valid():
        if form.cleaned_data['weir']:
            water_levels = water_levels.filter(weir=form.cleaned_data['weir'])
        if form.cleaned_data['start_date']:
            water_levels = water_levels.filter(record_date__gte=form.cleaned_data['start_date'])
        if form.cleaned_data['end_date']:
            water_levels = water_levels.filter(record_date__lte=form.cleaned_data['end_date'])

    stats = water_levels.aggregate(
        avg_water_level=Avg('water_level'),
        avg_flow_rate=Avg('flow_rate'),
        total_records=Count('id')
    )

    context = {
        'water_levels': water_levels,
        'filter_form': form,
        'avg_water_level': round(stats['avg_water_level'] or 0, 2),
        'avg_flow_rate': round(stats['avg_flow_rate'] or 0, 2),
        'total_records': stats['total_records'] or 0,
    }
    return render(request, 'water_level/list.html', context)


def water_level_create(request):
    if request.method == 'POST':
        form = WaterLevelForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, '水位记录创建成功！')
                return redirect('water_level_list')
            except Exception as e:
                messages.error(request, f'保存失败：{e}')
    else:
        initial = {'record_date': timezone.now().date()}
        weir_id = request.GET.get('weir')
        if weir_id:
            initial['weir'] = weir_id
        form = WaterLevelForm(initial=initial)
    context = {'form': form, 'title': '新增水位记录'}
    return render(request, 'water_level/form.html', context)


def water_level_edit(request, pk):
    water_level = get_object_or_404(WaterLevel, pk=pk)
    if request.method == 'POST':
        form = WaterLevelForm(request.POST, instance=water_level)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, '水位记录更新成功！')
                return redirect('water_level_list')
            except Exception as e:
                messages.error(request, f'保存失败：{e}')
    else:
        form = WaterLevelForm(instance=water_level)
    context = {'form': form, 'title': '编辑水位记录', 'water_level': water_level}
    return render(request, 'water_level/form.html', context)


def water_level_delete(request, pk):
    water_level = get_object_or_404(WaterLevel, pk=pk)
    if request.method == 'POST':
        water_level.delete()
        messages.success(request, '水位记录删除成功！')
        return redirect('water_level_list')
    context = {'water_level': water_level, 'title': '删除水位记录'}
    return render(request, 'water_level/delete.html', context)


def gate_status_list(request):
    form = ReportFilterForm(request.GET or None)
    gate_statuses = GateStatus.objects.select_related('weir').all().order_by('-change_time')

    if form.is_valid():
        if form.cleaned_data['weir']:
            gate_statuses = gate_statuses.filter(weir=form.cleaned_data['weir'])
        if form.cleaned_data['start_date']:
            gate_statuses = gate_statuses.filter(change_time__date__gte=form.cleaned_data['start_date'])
        if form.cleaned_data['end_date']:
            gate_statuses = gate_statuses.filter(change_time__date__lte=form.cleaned_data['end_date'])

    context = {'gate_statuses': gate_statuses, 'filter_form': form}
    return render(request, 'gate/list.html', context)


def gate_status_create(request):
    if request.method == 'POST':
        form = GateStatusForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '闸口状态创建成功！收获估算已自动重新计算。')
            return redirect('gate_status_list')
    else:
        initial = {'change_time': timezone.now()}
        weir_id = request.GET.get('weir')
        if weir_id:
            initial['weir'] = weir_id
        form = GateStatusForm(initial=initial)
    context = {'form': form, 'title': '新增闸口状态'}
    return render(request, 'gate/form.html', context)


def gate_status_edit(request, pk):
    gate_status = get_object_or_404(GateStatus, pk=pk)
    if request.method == 'POST':
        form = GateStatusForm(request.POST, instance=gate_status)
        if form.is_valid():
            form.save()
            messages.success(request, '闸口状态更新成功！收获估算已自动重新计算。')
            return redirect('gate_status_list')
    else:
        form = GateStatusForm(instance=gate_status)
    context = {'form': form, 'title': '编辑闸口状态', 'gate_status': gate_status}
    return render(request, 'gate/form.html', context)


def gate_status_delete(request, pk):
    gate_status = get_object_or_404(GateStatus, pk=pk)
    if request.method == 'POST':
        gate_status.delete()
        messages.success(request, '闸口状态删除成功！')
        return redirect('gate_status_list')
    context = {'gate_status': gate_status, 'title': '删除闸口状态'}
    return render(request, 'gate/delete.html', context)


def harvest_list(request):
    form = ReportFilterForm(request.GET or None)
    harvests = HarvestRecord.objects.select_related('weir').all().order_by('-record_date', '-created_at')

    if form.is_valid():
        if form.cleaned_data['weir']:
            harvests = harvests.filter(weir=form.cleaned_data['weir'])
        if form.cleaned_data['start_date']:
            harvests = harvests.filter(record_date__gte=form.cleaned_data['start_date'])
        if form.cleaned_data['end_date']:
            harvests = harvests.filter(record_date__lte=form.cleaned_data['end_date'])

    total_weight = harvests.aggregate(total=Sum('weight'))['total'] or 0
    total_quantity = harvests.aggregate(total=Sum('quantity'))['total'] or 0

    context = {
        'harvests': harvests,
        'filter_form': form,
        'total_weight': round(total_weight, 2),
        'total_quantity': total_quantity,
    }
    return render(request, 'harvest/list.html', context)


def harvest_create(request):
    if request.method == 'POST':
        form = HarvestRecordForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '收获记录创建成功！')
            return redirect('harvest_list')
    else:
        initial = {'record_date': timezone.now().date()}
        weir_id = request.GET.get('weir')
        if weir_id:
            initial['weir'] = weir_id
        form = HarvestRecordForm(initial=initial)
    context = {'form': form, 'title': '新增收获记录'}
    return render(request, 'harvest/form.html', context)


def harvest_edit(request, pk):
    harvest = get_object_or_404(HarvestRecord, pk=pk)
    if request.method == 'POST':
        form = HarvestRecordForm(request.POST, instance=harvest)
        if form.is_valid():
            form.save()
            messages.success(request, '收获记录更新成功！')
            return redirect('harvest_list')
    else:
        form = HarvestRecordForm(instance=harvest)
    context = {'form': form, 'title': '编辑收获记录', 'harvest': harvest}
    return render(request, 'harvest/form.html', context)


def harvest_delete(request, pk):
    harvest = get_object_or_404(HarvestRecord, pk=pk)
    if request.method == 'POST':
        harvest.delete()
        messages.success(request, '收获记录删除成功！')
        return redirect('harvest_list')
    context = {'harvest': harvest, 'title': '删除收获记录'}
    return render(request, 'harvest/delete.html', context)


def fish_school_list(request):
    form = ReportFilterForm(request.GET or None)
    fish_schools = FishSchool.objects.select_related('weir').all().order_by('-record_date', '-observe_time')

    if form.is_valid():
        if form.cleaned_data['weir']:
            fish_schools = fish_schools.filter(weir=form.cleaned_data['weir'])
        if form.cleaned_data['start_date']:
            fish_schools = fish_schools.filter(record_date__gte=form.cleaned_data['start_date'])
        if form.cleaned_data['end_date']:
            fish_schools = fish_schools.filter(record_date__lte=form.cleaned_data['end_date'])

    context = {'fish_schools': fish_schools, 'filter_form': form}
    return render(request, 'fish_school/list.html', context)


def fish_school_create(request):
    if request.method == 'POST':
        form = FishSchoolForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '鱼群记录创建成功！')
            return redirect('fish_school_list')
    else:
        initial = {
            'record_date': timezone.now().date(),
            'observe_time': timezone.now().time(),
        }
        weir_id = request.GET.get('weir')
        if weir_id:
            initial['weir'] = weir_id
        form = FishSchoolForm(initial=initial)
    context = {'form': form, 'title': '新增鱼群记录'}
    return render(request, 'fish_school/form.html', context)


def fish_school_edit(request, pk):
    fish_school = get_object_or_404(FishSchool, pk=pk)
    if request.method == 'POST':
        form = FishSchoolForm(request.POST, instance=fish_school)
        if form.is_valid():
            form.save()
            messages.success(request, '鱼群记录更新成功！')
            return redirect('fish_school_list')
    else:
        form = FishSchoolForm(instance=fish_school)
    context = {'form': form, 'title': '编辑鱼群记录', 'fish_school': fish_school}
    return render(request, 'fish_school/form.html', context)


def fish_school_delete(request, pk):
    fish_school = get_object_or_404(FishSchool, pk=pk)
    if request.method == 'POST':
        fish_school.delete()
        messages.success(request, '鱼群记录删除成功！')
        return redirect('fish_school_list')
    context = {'fish_school': fish_school, 'title': '删除鱼群记录'}
    return render(request, 'fish_school/delete.html', context)


def report_monthly_trend(request):
    form = ReportFilterForm(request.GET or None)
    weir = form.cleaned_data.get('weir') if form.is_valid() else None
    start_date = form.cleaned_data.get('start_date') if form.is_valid() else None
    end_date = form.cleaned_data.get('end_date') if form.is_valid() else None

    trend_data = get_monthly_trend(weir=weir, start_date=start_date, end_date=end_date)
    
    for d in trend_data:
        d['diff'] = round(d['actual'] - d['estimated'], 2)

    chart_labels = [d['month'] for d in trend_data]
    chart_estimated = [d['estimated'] for d in trend_data]
    chart_actual = [d['actual'] for d in trend_data]

    total_estimated = sum(d['estimated'] for d in trend_data)
    total_actual = sum(d['actual'] for d in trend_data)

    context = {
        'title': '月度收获趋势',
        'filter_form': form,
        'data_list': trend_data,
        'chart_labels': json.dumps(chart_labels),
        'chart_estimated': json.dumps(chart_estimated),
        'chart_actual': json.dumps(chart_actual),
        'total_estimated': round(total_estimated, 2),
        'total_actual': round(total_actual, 2),
    }
    return render(request, 'reports/monthly_trend.html', context)


def report_gate_comparison(request):
    form = ReportFilterForm(request.GET or None)
    weir = form.cleaned_data.get('weir') if form.is_valid() else None
    start_date = form.cleaned_data.get('start_date') if form.is_valid() else None
    end_date = form.cleaned_data.get('end_date') if form.is_valid() else None

    comparison_data = get_gate_strategy_comparison(weir=weir, start_date=start_date, end_date=end_date)
    
    for d in comparison_data:
        d['accuracy'] = d['avg_accuracy']

    chart_labels = [d['strategy'][:20] + '...' if len(d['strategy']) > 20 else d['strategy'] for d in comparison_data]
    chart_avg_actual = [d['avg_actual'] for d in comparison_data]
    chart_avg_estimated = [d['avg_estimated'] for d in comparison_data]
    chart_accuracy = [d['avg_accuracy'] or 0 for d in comparison_data]

    context = {
        'title': '闸口策略对比',
        'filter_form': form,
        'data_list': comparison_data,
        'chart_labels': json.dumps(chart_labels),
        'chart_avg_actual': json.dumps(chart_avg_actual),
        'chart_avg_estimated': json.dumps(chart_avg_estimated),
        'chart_accuracy': json.dumps(chart_accuracy),
    }
    return render(request, 'reports/gate_comparison.html', context)


def report_efficiency(request):
    from django.core.paginator import Paginator

    form = ReportFilterForm(request.GET or None)
    weir = form.cleaned_data.get('weir') if form.is_valid() else None
    start_date = form.cleaned_data.get('start_date') if form.is_valid() else None
    end_date = form.cleaned_data.get('end_date') if form.is_valid() else None

    estimates = HarvestEstimate.objects.filter(has_water_data=True).select_related('weir')

    if weir:
        estimates = estimates.filter(weir=weir)
    if start_date:
        estimates = estimates.filter(estimate_date__gte=start_date)
    if end_date:
        estimates = estimates.filter(estimate_date__lte=end_date)

    estimates = estimates.order_by('-estimate_date', 'weir__code')

    total_estimated = estimates.aggregate(total=Sum('estimated_weight'))['total'] or 0
    total_actual = estimates.aggregate(total=Sum('actual_weight'))['total'] or 0
    valid_estimates = estimates.filter(accuracy__isnull=False)
    avg_accuracy = valid_estimates.aggregate(avg=Avg('accuracy'))['avg']
    if avg_accuracy:
        avg_accuracy = round(avg_accuracy, 2)

    paginator = Paginator(estimates, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    filter_params = []
    if weir:
        filter_params.append(f'weir={weir.pk}')
    if start_date:
        filter_params.append(f'start_date={start_date}')
    if end_date:
        filter_params.append(f'end_date={end_date}')

    context = {
        'title': '效率估算报表',
        'filter_form': form,
        'estimates': page_obj.object_list,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'filter_params': '&'.join(filter_params),
        'total_estimated': round(total_estimated, 2),
        'total_actual': round(total_actual, 2),
        'avg_accuracy': avg_accuracy,
    }
    return render(request, 'reports/efficiency_estimate.html', context)


def recalculate_estimates_view(request, weir_id=None):
    if weir_id:
        weir = get_object_or_404(Weir, pk=weir_id)
        earliest = WaterLevel.objects.filter(weir=weir).order_by('record_date').first()
        if earliest:
            recalculate_estimates(weir, earliest.record_date)
            messages.success(request, f'{weir.code} 的收获估算已重新计算！')
        else:
            messages.warning(request, '该鱼梁暂无水位记录，无法计算。')
        return redirect('weir_detail', pk=weir_id)
    else:
        count = recalculate_all_estimates()
        messages.success(request, f'已重新计算所有鱼梁的收获估算，共 {len(count)} 条记录。')
        return redirect('report_efficiency')


def report_comprehensive_analysis(request):
    form = ComprehensiveFilterForm(request.GET or None)
    filters = {}

    if form.is_valid():
        filters = {
            'weir': form.cleaned_data.get('weir'),
            'start_date': form.cleaned_data.get('start_date'),
            'end_date': form.cleaned_data.get('end_date'),
            'season': form.cleaned_data.get('season'),
            'months': form.cleaned_data.get('months'),
            'water_level_min': form.cleaned_data.get('water_level_min'),
            'water_level_max': form.cleaned_data.get('water_level_max'),
            'flow_rate_min': form.cleaned_data.get('flow_rate_min'),
            'flow_rate_max': form.cleaned_data.get('flow_rate_max'),
            'weather': form.cleaned_data.get('weather'),
            'gate_strategy': form.cleaned_data.get('gate_strategy'),
            'gate_status': form.cleaned_data.get('gate_status'),
        }

    summary = get_comprehensive_analysis(filters)
    seasonal_data = get_seasonal_analysis(filters)
    water_level_data = get_water_level_interval_analysis(filters)
    flow_rate_data = get_flow_rate_analysis(filters)
    weather_data = get_weather_analysis(filters)
    monthly_data = get_monthly_comparison(filters)
    heatmap_data = get_strategy_heatmap_data(filters)
    multi_dim_data = get_multi_dimensional_comparison(filters)

    season_labels = [d['season_name'] for d in seasonal_data]
    season_efficiency = [d['efficiency'] for d in seasonal_data]
    season_actual = [d['total_actual'] for d in seasonal_data]

    water_labels = [d['interval'] for d in water_level_data]
    water_efficiency = [d['efficiency'] for d in water_level_data]
    water_actual = [d['total_actual'] for d in water_level_data]

    flow_labels = [d['interval'] for d in flow_rate_data]
    flow_efficiency = [d['efficiency'] for d in flow_rate_data]

    weather_labels = [d['weather'] for d in weather_data]
    weather_efficiency = [d['efficiency'] for d in weather_data]

    month_labels = [d['month'] for d in monthly_data]
    month_actual = [d['total_actual'] for d in monthly_data]
    month_estimated = [d['total_estimated'] for d in monthly_data]

    heatmap_seasons = list(set([d['season'] for d in heatmap_data]))
    heatmap_water_levels = list(set([d['water_level'] for d in heatmap_data]))
    heatmap_values = []
    for season in heatmap_seasons:
        row = []
        for wl in heatmap_water_levels:
            val = next((d['efficiency'] for d in heatmap_data if d['season'] == season and d['water_level'] == wl), 0)
            row.append(val)
        heatmap_values.append(row)

    multi_dim_categories = list(set([d['category'] for d in multi_dim_data]))
    multi_dim_labels = [d['group'] for d in multi_dim_data]
    multi_dim_efficiency = [d['efficiency'] for d in multi_dim_data]
    multi_dim_category_colors = []
    color_map = {
        '季节': 'rgba(46, 125, 50, 0.7)',
        '水位区间': 'rgba(30, 58, 95, 0.7)',
        '流速区间': 'rgba(201, 162, 39, 0.7)',
        '天气': 'rgba(156, 39, 176, 0.7)',
        '闸口策略': 'rgba(211, 47, 47, 0.7)',
    }
    for d in multi_dim_data:
        multi_dim_category_colors.append(color_map.get(d['category'], 'rgba(100, 100, 100, 0.7)'))

    has_data = summary.get('record_count', 0) > 0

    context = {
        'title': '综合筛选分析',
        'filter_form': form,
        'summary': summary,
        'has_data': has_data,
        'seasonal_data': seasonal_data,
        'water_level_data': water_level_data,
        'flow_rate_data': flow_rate_data,
        'weather_data': weather_data,
        'monthly_data': monthly_data,
        'heatmap_data': heatmap_data,
        'multi_dim_data': multi_dim_data,
        'season_labels': json.dumps(season_labels),
        'season_efficiency': json.dumps(season_efficiency),
        'season_actual': json.dumps(season_actual),
        'water_labels': json.dumps(water_labels),
        'water_efficiency': json.dumps(water_efficiency),
        'water_actual': json.dumps(water_actual),
        'flow_labels': json.dumps(flow_labels),
        'flow_efficiency': json.dumps(flow_efficiency),
        'weather_labels': json.dumps(weather_labels),
        'weather_efficiency': json.dumps(weather_efficiency),
        'month_labels': json.dumps(month_labels),
        'month_actual': json.dumps(month_actual),
        'month_estimated': json.dumps(month_estimated),
        'heatmap_seasons': json.dumps(heatmap_seasons),
        'heatmap_water_levels': json.dumps(heatmap_water_levels),
        'heatmap_values': json.dumps(heatmap_values),
        'multi_dim_labels': json.dumps(multi_dim_labels),
        'multi_dim_efficiency': json.dumps(multi_dim_efficiency),
        'multi_dim_category_colors': json.dumps(multi_dim_category_colors),
        'multi_dim_categories': json.dumps(multi_dim_categories),
    }
    return render(request, 'reports/comprehensive_analysis.html', context)


def report_strategy_comparison(request):
    form = ComprehensiveFilterForm(request.GET or None)
    filters = {}

    if form.is_valid():
        filters = {
            'weir': form.cleaned_data.get('weir'),
            'start_date': form.cleaned_data.get('start_date'),
            'end_date': form.cleaned_data.get('end_date'),
            'season': form.cleaned_data.get('season'),
            'months': form.cleaned_data.get('months'),
            'water_level_min': form.cleaned_data.get('water_level_min'),
            'water_level_max': form.cleaned_data.get('water_level_max'),
            'flow_rate_min': form.cleaned_data.get('flow_rate_min'),
            'flow_rate_max': form.cleaned_data.get('flow_rate_max'),
            'weather': form.cleaned_data.get('weather'),
            'gate_strategy': form.cleaned_data.get('gate_strategy'),
            'gate_status': form.cleaned_data.get('gate_status'),
        }

    strategy_data = get_strategy_efficiency_comparison(filters)
    comprehensive_analysis = get_comprehensive_strategy_analysis(filters)

    strategy_labels = []
    for d in strategy_data:
        label = d['strategy'][:15] + '...' if len(d['strategy']) > 15 else d['strategy']
        strategy_labels.append(label)

    strategy_efficiency = [d['efficiency'] for d in strategy_data]
    strategy_actual = [d['avg_actual'] if 'avg_actual' in d else d['total_actual'] / d['count'] if d['count'] > 0 else 0 for d in strategy_data]
    strategy_accuracy = [d['avg_accuracy'] or 0 for d in strategy_data]
    strategy_count = [d['count'] for d in strategy_data]
    strategy_avg_water = [d['avg_water_level'] for d in strategy_data]
    strategy_avg_flow = [d['avg_flow_rate'] for d in strategy_data]

    radar_datasets = []
    for i, analysis in enumerate(comprehensive_analysis[:3]):
        seasonal_eff = {item['season']: item['efficiency'] for item in analysis['seasonal_breakdown']}
        water_eff = {item['interval']: item['efficiency'] for item in analysis['water_breakdown']}
        
        radar_data = [
            seasonal_eff.get('spring', 0),
            seasonal_eff.get('summer', 0),
            seasonal_eff.get('autumn', 0),
            seasonal_eff.get('winter', 0),
            water_eff.get('0-1米', 0),
            water_eff.get('1-2米', 0),
            water_eff.get('2-3米', 0),
            water_eff.get('3-4米', 0),
        ]
        
        colors = [
            ('rgba(255, 193, 7, 0.2)', 'rgba(255, 193, 7, 1)'),
            ('rgba(192, 192, 192, 0.2)', 'rgba(192, 192, 192, 1)'),
            ('rgba(205, 127, 50, 0.2)', 'rgba(205, 127, 50, 1)'),
        ]
        bg_color, border_color = colors[i] if i < len(colors) else colors[-1]
        
        radar_datasets.append({
            'label': strategy_labels[i],
            'data': radar_data,
            'backgroundColor': bg_color,
            'borderColor': border_color,
            'borderWidth': 2,
        })

    radar_labels = ['春季', '夏季', '秋季', '冬季', '0-1米', '1-2米', '2-3米', '3-4米']

    context = {
        'title': '闸口策略对比分析',
        'filter_form': form,
        'strategy_data': strategy_data,
        'comprehensive_analysis': comprehensive_analysis,
        'strategy_labels': json.dumps(strategy_labels),
        'strategy_efficiency': json.dumps(strategy_efficiency),
        'strategy_actual': json.dumps(strategy_actual),
        'strategy_accuracy': json.dumps(strategy_accuracy),
        'strategy_count': json.dumps(strategy_count),
        'strategy_avg_water': json.dumps(strategy_avg_water),
        'strategy_avg_flow': json.dumps(strategy_avg_flow),
        'radar_labels': json.dumps(radar_labels),
        'radar_datasets': json.dumps(radar_datasets),
    }
    return render(request, 'reports/strategy_comparison.html', context)


def report_simulation(request):
    form = SimulationForm(request.POST or None)
    simulation_result = None
    multi_strategy_results = None
    historical_reconstruction = None
    typical_configs = None
    fishing_calendar = None
    operation_patterns = None

    weir = None
    if request.method == 'POST' and form.is_valid():
        weir = form.cleaned_data['weir']
        sim_date = form.cleaned_data['simulation_date']
        water_level = form.cleaned_data['water_level']
        flow_rate = form.cleaned_data['flow_rate']
        weather = form.cleaned_data['weather']
        gate_config = form.cleaned_data['gate_config']
        historical_period = form.cleaned_data['historical_period']
        simulation_mode = request.POST.get('simulation_mode', 'single')

        if simulation_mode == 'single':
            simulation_result = simulate_harvest(
                weir=weir,
                sim_date=sim_date,
                water_level=water_level,
                flow_rate=flow_rate,
                weather=weather,
                gate_config=gate_config,
                historical_period=historical_period
            )
        elif simulation_mode == 'multi':
            additional_strategies = request.POST.get('additional_strategies', '')
            strategies = [s.strip() for s in additional_strategies.split('\n') if s.strip()]
            if gate_config and gate_config not in strategies:
                strategies.insert(0, gate_config)
            
            if strategies:
                multi_strategy_results = simulate_multiple_strategies(
                    weir=weir,
                    sim_date=sim_date,
                    water_level=water_level,
                    flow_rate=flow_rate,
                    weather=weather,
                    strategies=strategies,
                    historical_period=historical_period
                )
        elif simulation_mode == 'reconstruct':
            reconstruct_date = form.cleaned_data['simulation_date']
            historical_reconstruction = reconstruct_historical_operation(weir, reconstruct_date)

    if weir or (request.method == 'GET' and Weir.objects.exists()):
        if not weir:
            weir = Weir.objects.exclude(code__startswith='T-').order_by('id').first()
            if not weir:
                weir = Weir.objects.first()
        
        typical_configs = get_typical_gate_configs(weir, top_n=5)
        fishing_calendar = get_traditional_fishing_calendar(weir)
        operation_patterns = get_historical_operation_patterns(weir)

    if multi_strategy_results:
        sorted_results = sorted(multi_strategy_results, key=lambda x: x['rank'])
        ms_labels = [r['strategy'] for r in sorted_results]
        ms_weights = [r['estimated_weight'] for r in sorted_results]
        ms_confidence = [r['confidence'] for r in sorted_results]
    else:
        ms_labels = []
        ms_weights = []
        ms_confidence = []

    context = {
        'title': '历史作业模拟推演',
        'form': form,
        'simulation_result': simulation_result,
        'multi_strategy_results': multi_strategy_results,
        'historical_reconstruction': historical_reconstruction,
        'typical_configs': typical_configs,
        'fishing_calendar': fishing_calendar,
        'operation_patterns': operation_patterns,
        'selected_weir': weir,
        'ms_labels': json.dumps(ms_labels),
        'ms_weights': json.dumps(ms_weights),
        'ms_confidence': json.dumps(ms_confidence),
    }
    return render(request, 'reports/simulation.html', context)


def report_fish_migration(request):
    form = FishMigrationFilterForm(request.GET or None)
    filters = {}

    if form.is_valid():
        filters = {
            'weir': form.cleaned_data.get('weir'),
            'start_date': form.cleaned_data.get('start_date'),
            'end_date': form.cleaned_data.get('end_date'),
            'season': form.cleaned_data.get('season'),
            'months': form.cleaned_data.get('months'),
            'water_level_min': form.cleaned_data.get('water_level_min'),
            'water_level_max': form.cleaned_data.get('water_level_max'),
            'weather': form.cleaned_data.get('weather'),
            'fish_species': form.cleaned_data.get('fish_species'),
        }

    analysis = get_comprehensive_migration_analysis(filters)

    monthly_trend = analysis['monthly_trend']
    month_labels = [d['month'] for d in monthly_trend]
    month_fish = [d['total_fish_estimated'] for d in monthly_trend]
    month_harvest = [d['harvest_weight'] for d in monthly_trend]
    month_conversion = [d['conversion_rate'] for d in monthly_trend]

    seasonal = analysis['seasonal_analysis']
    season_labels = [d['season_name'] for d in seasonal]
    season_fish = [d['total_fish_estimated'] for d in seasonal]
    season_harvest = [d['harvest_weight'] for d in seasonal]
    season_conversion = [d['conversion_rate'] for d in seasonal]

    water_level = analysis['water_level_analysis']
    water_labels = [d['interval'] for d in water_level]
    water_fish = [d['total_fish_estimated'] for d in water_level]
    water_harvest = [d['harvest_weight'] for d in water_level]
    water_conversion = [d['conversion_rate'] for d in water_level]

    weather = analysis['weather_analysis']
    weather_labels = [d['weather'] for d in weather]
    weather_fish = [d['total_fish_estimated'] for d in weather]
    weather_harvest = [d['harvest_weight'] for d in weather]
    weather_conversion = [d['conversion_rate'] for d in weather]

    species = analysis['species_analysis'][:10]
    species_labels = [d['species'] for d in species]
    species_fish = [d['total_fish_estimated'] for d in species]
    species_harvest = [d['harvest_weight'] for d in species]

    key_factors = analysis['key_factors']
    factor_labels = [f['factor'][:15] + '...' if len(f['factor']) > 15 else f['factor'] for f in key_factors]
    factor_scores = [f['score'] for f in key_factors]
    factor_category_colors = []
    color_map = {
        '生态关联': 'rgba(46, 125, 50, 0.7)',
        '水文因子': 'rgba(30, 58, 95, 0.7)',
        '季节因子': 'rgba(201, 162, 39, 0.7)',
        '天气因子': 'rgba(156, 39, 176, 0.7)',
    }
    for f in key_factors:
        factor_category_colors.append(color_map.get(f['category'], 'rgba(100, 100, 100, 0.7)'))

    correlations = analysis['correlations']
    radar_labels = [
        '鱼群-收获关联', '水位-鱼群关联', '流速-鱼群关联',
        '水位-收获关联', '流速-收获关联'
    ]
    radar_values = [
        abs(correlations['fish_harvest_correlation'] or 0) * 100,
        abs(correlations['water_level_fish_correlation'] or 0) * 100,
        abs(correlations['flow_rate_fish_correlation'] or 0) * 100,
        abs(correlations['water_level_harvest_correlation'] or 0) * 100,
        abs(correlations['flow_rate_harvest_correlation'] or 0) * 100,
    ]

    has_data = analysis['has_data']

    context = {
        'title': '鱼梁生态响应与鱼汛预警分析',
        'filter_form': form,
        'has_data': has_data,
        'fish_summary': analysis['fish_summary'],
        'harvest_summary': analysis['harvest_summary'],
        'correlations': correlations,
        'key_factors': key_factors,
        'warnings': analysis['warnings'],
        'seasonal_analysis': seasonal,
        'water_level_analysis': water_level,
        'weather_analysis': weather,
        'species_analysis': species,
        'month_labels': json.dumps(month_labels),
        'month_fish': json.dumps(month_fish),
        'month_harvest': json.dumps(month_harvest),
        'month_conversion': json.dumps(month_conversion),
        'season_labels': json.dumps(season_labels),
        'season_fish': json.dumps(season_fish),
        'season_harvest': json.dumps(season_harvest),
        'season_conversion': json.dumps(season_conversion),
        'water_labels': json.dumps(water_labels),
        'water_fish': json.dumps(water_fish),
        'water_harvest': json.dumps(water_harvest),
        'water_conversion': json.dumps(water_conversion),
        'weather_labels': json.dumps(weather_labels),
        'weather_fish': json.dumps(weather_fish),
        'weather_harvest': json.dumps(weather_harvest),
        'weather_conversion': json.dumps(weather_conversion),
        'species_labels': json.dumps(species_labels),
        'species_fish': json.dumps(species_fish),
        'species_harvest': json.dumps(species_harvest),
        'factor_labels': json.dumps(factor_labels),
        'factor_scores': json.dumps(factor_scores),
        'factor_category_colors': json.dumps(factor_category_colors),
        'radar_labels': json.dumps(radar_labels),
        'radar_values': json.dumps(radar_values),
    }
    return render(request, 'reports/fish_migration_analysis.html', context)
