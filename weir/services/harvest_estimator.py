from datetime import timedelta
from django.db.models import Avg, Sum
from django.utils import timezone
from ..models import Weir, WaterLevel, GateStatus, HarvestRecord, HarvestEstimate


def get_season_factor(date):
    month = date.month
    if month in [3, 4, 5]:
        return 1.3
    elif month in [6, 7, 8]:
        return 1.5
    elif month in [9, 10, 11]:
        return 1.1
    else:
        return 0.8


def get_water_level_factor(water_level):
    if water_level < 1.0:
        return 0.5
    elif water_level < 2.0:
        return 0.8
    elif water_level < 3.0:
        return 1.2
    elif water_level < 4.0:
        return 1.5
    else:
        return 1.0


def get_active_gate_strategy(weir, target_date):
    gate_statuses = GateStatus.objects.filter(
        weir=weir,
        change_time__date__lte=target_date
    ).order_by('gate_number', '-change_time')

    latest_status = {}
    for gs in gate_statuses:
        if gs.gate_number not in latest_status:
            latest_status[gs.gate_number] = gs.status

    if not latest_status:
        return '默认策略'

    strategy_parts = []
    for gate_num in sorted(latest_status.keys()):
        status = '开' if latest_status[gate_num] == 'open' else '关'
        strategy_parts.append(f'{gate_num}{status}')

    return ', '.join(strategy_parts)


def get_actual_weight_for_date(weir, target_date):
    actual = HarvestRecord.objects.filter(
        weir=weir,
        record_date=target_date
    ).aggregate(total=Sum('weight'))['total']
    return actual or 0.0


def estimate_single_day(weir, estimate_date):
    water_level_record = WaterLevel.objects.filter(
        weir=weir,
        record_date=estimate_date,
        is_primary=True
    ).first()

    if not water_level_record:
        return {
            'weir': weir,
            'estimate_date': estimate_date,
            'estimated_weight': 0,
            'gate_strategy': '无水位数据',
            'water_level': None,
            'has_water_data': False,
            'actual_weight': get_actual_weight_for_date(weir, estimate_date),
        }

    gate_strategy = get_active_gate_strategy(weir, estimate_date)
    water_level = water_level_record.water_level

    similar_records = HarvestRecord.objects.filter(
        weir=weir,
        record_date__month=estimate_date.month,
        record_date__year__lte=estimate_date.year
    )

    similar_with_water = []
    for record in similar_records:
        wl = WaterLevel.objects.filter(
            weir=weir,
            record_date=record.record_date,
            is_primary=True
        ).first()
        if wl and abs(wl.water_level - water_level) <= 0.5:
            strategy = get_active_gate_strategy(weir, record.record_date)
            if strategy == gate_strategy:
                similar_with_water.append(record.weight)

    if similar_with_water:
        avg_weight = sum(similar_with_water) / len(similar_with_water)
        season_factor = get_season_factor(estimate_date)
        water_factor = get_water_level_factor(water_level)
        estimated_weight = round(avg_weight * season_factor * water_factor, 2)
    else:
        baseline = water_level * 2.0
        season_factor = get_season_factor(estimate_date)
        estimated_weight = round(baseline * season_factor, 2)

    return {
        'weir': weir,
        'estimate_date': estimate_date,
        'estimated_weight': estimated_weight,
        'gate_strategy': gate_strategy,
        'water_level': water_level,
        'has_water_data': True,
        'actual_weight': get_actual_weight_for_date(weir, estimate_date),
    }


def save_estimate(estimate_data):
    estimate, created = HarvestEstimate.objects.update_or_create(
        weir=estimate_data['weir'],
        estimate_date=estimate_data['estimate_date'],
        defaults={
            'estimated_weight': estimate_data['estimated_weight'],
            'gate_strategy': estimate_data['gate_strategy'],
            'water_level': estimate_data['water_level'],
            'has_water_data': estimate_data['has_water_data'],
            'actual_weight': estimate_data['actual_weight'],
        }
    )
    return estimate


def recalculate_estimates(weir, start_date, end_date=None):
    if end_date is None:
        end_date = timezone.now().date()

    current_date = start_date
    estimates = []

    while current_date <= end_date:
        estimate_data = estimate_single_day(weir, current_date)
        estimate = save_estimate(estimate_data)
        estimates.append(estimate)
        current_date += timedelta(days=1)

    return estimates


def recalculate_all_estimates():
    estimates = []
    for weir in Weir.objects.all():
        earliest_record = WaterLevel.objects.filter(
            weir=weir
        ).order_by('record_date').first()
        if earliest_record:
            estimates.extend(
                recalculate_estimates(weir, earliest_record.record_date)
            )
    return estimates


def get_monthly_trend(weir=None, start_date=None, end_date=None):
    queryset = HarvestEstimate.objects.filter(has_water_data=True)

    if weir:
        queryset = queryset.filter(weir=weir)
    if start_date:
        queryset = queryset.filter(estimate_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(estimate_date__lte=end_date)

    monthly_data = {}
    for estimate in queryset:
        month_key = estimate.estimate_date.strftime('%Y-%m')
        if month_key not in monthly_data:
            monthly_data[month_key] = {
                'month': month_key,
                'estimated': 0,
                'actual': 0,
                'count': 0,
            }
        monthly_data[month_key]['estimated'] += estimate.estimated_weight
        monthly_data[month_key]['actual'] += estimate.actual_weight
        monthly_data[month_key]['count'] += 1

    return sorted(monthly_data.values(), key=lambda x: x['month'])


def get_gate_strategy_comparison(weir=None, start_date=None, end_date=None):
    queryset = HarvestEstimate.objects.filter(has_water_data=True)

    if weir:
        queryset = queryset.filter(weir=weir)
    if start_date:
        queryset = queryset.filter(estimate_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(estimate_date__lte=end_date)

    strategy_data = {}
    for estimate in queryset:
        strategy = estimate.gate_strategy or '未知策略'
        if strategy not in strategy_data:
            strategy_data[strategy] = {
                'strategy': strategy,
                'total_estimated': 0,
                'total_actual': 0,
                'avg_estimated': 0,
                'avg_actual': 0,
                'count': 0,
                'avg_accuracy': 0,
            }
        strategy_data[strategy]['total_estimated'] += estimate.estimated_weight
        strategy_data[strategy]['total_actual'] += estimate.actual_weight
        strategy_data[strategy]['count'] += 1
        if estimate.accuracy is not None:
            strategy_data[strategy]['avg_accuracy'] += estimate.accuracy

    for strategy, data in strategy_data.items():
        if data['count'] > 0:
            data['avg_estimated'] = round(data['total_estimated'] / data['count'], 2)
            data['avg_actual'] = round(data['total_actual'] / data['count'], 2)
            data['avg_accuracy'] = round(data['avg_accuracy'] / data['count'], 2)
        data['total_estimated'] = round(data['total_estimated'], 2)
        data['total_actual'] = round(data['total_actual'], 2)

    return sorted(strategy_data.values(), key=lambda x: -x['avg_actual'])
