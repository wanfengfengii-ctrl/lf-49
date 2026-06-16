from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta
import json
from .models import Weir, WaterLevel, GateStatus, HarvestRecord, FishSchool, HarvestEstimate
from .forms import (
    WeirForm, WaterLevelForm, GateStatusForm, HarvestRecordForm,
    FishSchoolForm, ReportFilterForm
)
from .services.harvest_estimator import (
    get_monthly_trend, get_gate_strategy_comparison,
    recalculate_estimates, recalculate_all_estimates
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
    form = ReportFilterForm(request.GET or None)
    water_levels = WaterLevel.objects.select_related('weir').all().order_by('-record_date', '-created_at')

    if form.is_valid():
        if form.cleaned_data['weir']:
            water_levels = water_levels.filter(weir=form.cleaned_data['weir'])
        if form.cleaned_data['start_date']:
            water_levels = water_levels.filter(record_date__gte=form.cleaned_data['start_date'])
        if form.cleaned_data['end_date']:
            water_levels = water_levels.filter(record_date__lte=form.cleaned_data['end_date'])

    context = {'water_levels': water_levels, 'filter_form': form}
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
