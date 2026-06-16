from datetime import timedelta, date
from django.db.models import Avg, Sum, Count, Q
from django.utils import timezone
from ..models import Weir, WaterLevel, GateStatus, HarvestRecord, HarvestEstimate, FishSchool


def get_season_factor(date):
    from datetime import datetime
    if isinstance(date, str):
        date = datetime.strptime(date, '%Y-%m-%d').date()
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


def get_season(month):
    if month in [3, 4, 5]:
        return 'spring'
    elif month in [6, 7, 8]:
        return 'summer'
    elif month in [9, 10, 11]:
        return 'autumn'
    else:
        return 'winter'


def get_season_name(season_code):
    season_names = {
        'spring': '春季',
        'summer': '夏季',
        'autumn': '秋季',
        'winter': '冬季',
    }
    return season_names.get(season_code, '未知')


def apply_comprehensive_filters(queryset, filters):
    if filters.get('weir'):
        queryset = queryset.filter(weir=filters['weir'])
    if filters.get('start_date'):
        queryset = queryset.filter(estimate_date__gte=filters['start_date'])
    if filters.get('end_date'):
        queryset = queryset.filter(estimate_date__lte=filters['end_date'])
    if filters.get('season'):
        season_months = []
        for s in filters['season']:
            if s == 'spring':
                season_months.extend([3, 4, 5])
            elif s == 'summer':
                season_months.extend([6, 7, 8])
            elif s == 'autumn':
                season_months.extend([9, 10, 11])
            elif s == 'winter':
                season_months.extend([12, 1, 2])
        if season_months:
            queryset = queryset.filter(estimate_date__month__in=season_months)
    if filters.get('months'):
        queryset = queryset.filter(estimate_date__month__in=[int(m) for m in filters['months']])
    if filters.get('water_level_min') is not None:
        queryset = queryset.filter(water_level__gte=filters['water_level_min'])
    if filters.get('water_level_max') is not None:
        queryset = queryset.filter(water_level__lte=filters['water_level_max'])
    if filters.get('gate_strategy'):
        queryset = queryset.filter(gate_strategy__icontains=filters['gate_strategy'])
    if filters.get('gate_status'):
        status_text = '开' if filters['gate_status'] == 'open' else '关'
        queryset = queryset.filter(gate_strategy__icontains=status_text)
    return queryset


def apply_water_level_filters(water_queryset, filters):
    if filters.get('weir'):
        water_queryset = water_queryset.filter(weir=filters['weir'])
    if filters.get('start_date'):
        water_queryset = water_queryset.filter(record_date__gte=filters['start_date'])
    if filters.get('end_date'):
        water_queryset = water_queryset.filter(record_date__lte=filters['end_date'])
    if filters.get('season'):
        season_months = []
        for s in filters['season']:
            if s == 'spring':
                season_months.extend([3, 4, 5])
            elif s == 'summer':
                season_months.extend([6, 7, 8])
            elif s == 'autumn':
                season_months.extend([9, 10, 11])
            elif s == 'winter':
                season_months.extend([12, 1, 2])
        if season_months:
            water_queryset = water_queryset.filter(record_date__month__in=season_months)
    if filters.get('months'):
        water_queryset = water_queryset.filter(record_date__month__in=[int(m) for m in filters['months']])
    if filters.get('water_level_min') is not None:
        water_queryset = water_queryset.filter(water_level__gte=filters['water_level_min'])
    if filters.get('water_level_max') is not None:
        water_queryset = water_queryset.filter(water_level__lte=filters['water_level_max'])
    if filters.get('flow_rate_min') is not None:
        water_queryset = water_queryset.filter(flow_rate__gte=filters['flow_rate_min'])
    if filters.get('flow_rate_max') is not None:
        water_queryset = water_queryset.filter(flow_rate__lte=filters['flow_rate_max'])
    if filters.get('weather'):
        water_queryset = water_queryset.filter(weather__in=filters['weather'])
    return water_queryset


def get_comprehensive_analysis(filters=None):
    filters = filters or {}

    queryset = HarvestEstimate.objects.filter(has_water_data=True)
    queryset = apply_comprehensive_filters(queryset, filters)

    water_queryset = WaterLevel.objects.filter(is_primary=True)
    water_queryset = apply_water_level_filters(water_queryset, filters)

    water_date_map = {}
    for wl in water_queryset:
        key = (wl.weir_id, wl.record_date)
        water_date_map[key] = wl

    estimates_with_water = []
    for est in queryset:
        key = (est.weir_id, est.estimate_date)
        if key in water_date_map:
            wl = water_date_map[key]
            estimates_with_water.append({
                'estimate': est,
                'water_level': wl.water_level,
                'flow_rate': wl.flow_rate,
                'weather': wl.weather,
            })

    total_estimated = queryset.aggregate(total=Sum('estimated_weight'))['total'] or 0
    total_actual = queryset.aggregate(total=Sum('actual_weight'))['total'] or 0
    record_count = queryset.count()
    avg_accuracy = queryset.filter(accuracy__isnull=False).aggregate(avg=Avg('accuracy'))['avg']

    return {
        'total_estimated': round(total_estimated, 2),
        'total_actual': round(total_actual, 2),
        'record_count': record_count,
        'avg_accuracy': round(avg_accuracy, 2) if avg_accuracy else None,
        'estimates_with_water': estimates_with_water,
    }


def get_seasonal_analysis(filters=None):
    filters = filters or {}

    queryset = HarvestEstimate.objects.filter(has_water_data=True)
    queryset = apply_comprehensive_filters(queryset, filters)

    water_queryset = WaterLevel.objects.filter(is_primary=True)
    water_queryset = apply_water_level_filters(water_queryset, filters)

    water_date_map = {}
    for wl in water_queryset:
        key = (wl.weir_id, wl.record_date)
        water_date_map[key] = wl

    seasonal_data = {}
    for est in queryset:
        key = (est.weir_id, est.estimate_date)
        if key not in water_date_map:
            continue

        wl = water_date_map[key]
        season = get_season(est.estimate_date.month)

        if season not in seasonal_data:
            seasonal_data[season] = {
                'season': season,
                'season_name': get_season_name(season),
                'total_estimated': 0,
                'total_actual': 0,
                'count': 0,
                'avg_water_level': 0,
                'avg_flow_rate': 0,
                'efficiency': 0,
            }

        seasonal_data[season]['total_estimated'] += est.estimated_weight
        seasonal_data[season]['total_actual'] += est.actual_weight
        seasonal_data[season]['count'] += 1
        seasonal_data[season]['avg_water_level'] += wl.water_level
        seasonal_data[season]['avg_flow_rate'] += wl.flow_rate

    for season, data in seasonal_data.items():
        if data['count'] > 0:
            data['avg_water_level'] = round(data['avg_water_level'] / data['count'], 2)
            data['avg_flow_rate'] = round(data['avg_flow_rate'] / data['count'], 2)
            data['total_estimated'] = round(data['total_estimated'], 2)
            data['total_actual'] = round(data['total_actual'], 2)
            data['efficiency'] = round(data['total_actual'] / data['count'], 2) if data['count'] > 0 else 0

    season_order = ['spring', 'summer', 'autumn', 'winter']
    return [seasonal_data[s] for s in season_order if s in seasonal_data]


def get_water_level_interval_analysis(filters=None):
    filters = filters or {}

    queryset = HarvestEstimate.objects.filter(has_water_data=True)
    queryset = apply_comprehensive_filters(queryset, filters)

    water_queryset = WaterLevel.objects.filter(is_primary=True)
    water_queryset = apply_water_level_filters(water_queryset, filters)

    water_date_map = {}
    for wl in water_queryset:
        key = (wl.weir_id, wl.record_date)
        water_date_map[key] = wl

    intervals = [
        (0, 1, '0-1米'),
        (1, 2, '1-2米'),
        (2, 3, '2-3米'),
        (3, 4, '3-4米'),
        (4, 100, '4米以上'),
    ]

    interval_data = {}
    for min_val, max_val, label in intervals:
        interval_data[label] = {
            'interval': label,
            'min_val': min_val,
            'max_val': max_val,
            'total_estimated': 0,
            'total_actual': 0,
            'count': 0,
            'efficiency': 0,
        }

    for est in queryset:
        key = (est.weir_id, est.estimate_date)
        if key not in water_date_map:
            continue

        wl = water_date_map[key]
        for min_val, max_val, label in intervals:
            if min_val <= wl.water_level < max_val:
                interval_data[label]['total_estimated'] += est.estimated_weight
                interval_data[label]['total_actual'] += est.actual_weight
                interval_data[label]['count'] += 1
                break

    for label, data in interval_data.items():
        if data['count'] > 0:
            data['total_estimated'] = round(data['total_estimated'], 2)
            data['total_actual'] = round(data['total_actual'], 2)
            data['efficiency'] = round(data['total_actual'] / data['count'], 2)

    return [interval_data[label] for _, _, label in intervals if interval_data[label]['count'] > 0]


def get_flow_rate_analysis(filters=None):
    filters = filters or {}

    queryset = HarvestEstimate.objects.filter(has_water_data=True)
    queryset = apply_comprehensive_filters(queryset, filters)

    water_queryset = WaterLevel.objects.filter(is_primary=True)
    water_queryset = apply_water_level_filters(water_queryset, filters)

    water_date_map = {}
    for wl in water_queryset:
        key = (wl.weir_id, wl.record_date)
        water_date_map[key] = wl

    intervals = [
        (0, 0.5, '0-0.5 m/s'),
        (0.5, 1, '0.5-1 m/s'),
        (1, 1.5, '1-1.5 m/s'),
        (1.5, 2, '1.5-2 m/s'),
        (2, 100, '2 m/s以上'),
    ]

    flow_data = {}
    for min_val, max_val, label in intervals:
        flow_data[label] = {
            'interval': label,
            'total_estimated': 0,
            'total_actual': 0,
            'count': 0,
            'efficiency': 0,
        }

    for est in queryset:
        key = (est.weir_id, est.estimate_date)
        if key not in water_date_map:
            continue

        wl = water_date_map[key]
        for min_val, max_val, label in intervals:
            if min_val <= wl.flow_rate < max_val:
                flow_data[label]['total_estimated'] += est.estimated_weight
                flow_data[label]['total_actual'] += est.actual_weight
                flow_data[label]['count'] += 1
                break

    for label, data in flow_data.items():
        if data['count'] > 0:
            data['total_estimated'] = round(data['total_estimated'], 2)
            data['total_actual'] = round(data['total_actual'], 2)
            data['efficiency'] = round(data['total_actual'] / data['count'], 2)

    return [flow_data[label] for _, _, label in intervals if flow_data[label]['count'] > 0]


def get_weather_analysis(filters=None):
    filters = filters or {}

    queryset = HarvestEstimate.objects.filter(has_water_data=True)
    queryset = apply_comprehensive_filters(queryset, filters)

    water_queryset = WaterLevel.objects.filter(is_primary=True)
    water_queryset = apply_water_level_filters(water_queryset, filters)

    water_date_map = {}
    for wl in water_queryset:
        key = (wl.weir_id, wl.record_date)
        water_date_map[key] = wl

    weather_data = {}
    for est in queryset:
        key = (est.weir_id, est.estimate_date)
        if key not in water_date_map:
            continue

        wl = water_date_map[key]
        weather = wl.weather

        if weather not in weather_data:
            weather_data[weather] = {
                'weather': weather,
                'total_estimated': 0,
                'total_actual': 0,
                'count': 0,
                'efficiency': 0,
            }

        weather_data[weather]['total_estimated'] += est.estimated_weight
        weather_data[weather]['total_actual'] += est.actual_weight
        weather_data[weather]['count'] += 1

    for weather, data in weather_data.items():
        if data['count'] > 0:
            data['total_estimated'] = round(data['total_estimated'], 2)
            data['total_actual'] = round(data['total_actual'], 2)
            data['efficiency'] = round(data['total_actual'] / data['count'], 2)

    return sorted(weather_data.values(), key=lambda x: -x['efficiency'])


def get_strategy_efficiency_comparison(filters=None):
    filters = filters or {}

    queryset = HarvestEstimate.objects.filter(has_water_data=True)
    queryset = apply_comprehensive_filters(queryset, filters)

    water_queryset = WaterLevel.objects.filter(is_primary=True)
    water_queryset = apply_water_level_filters(water_queryset, filters)

    water_date_map = {}
    for wl in water_queryset:
        key = (wl.weir_id, wl.record_date)
        water_date_map[key] = wl

    strategy_data = {}
    for est in queryset:
        key = (est.weir_id, est.estimate_date)
        if key not in water_date_map:
            continue

        wl = water_date_map[key]
        strategy = est.gate_strategy or '未知策略'

        if strategy not in strategy_data:
            strategy_data[strategy] = {
                'strategy': strategy,
                'total_estimated': 0,
                'total_actual': 0,
                'count': 0,
                'avg_accuracy': 0,
                'avg_water_level': 0,
                'avg_flow_rate': 0,
                'efficiency': 0,
            }

        strategy_data[strategy]['total_estimated'] += est.estimated_weight
        strategy_data[strategy]['total_actual'] += est.actual_weight
        strategy_data[strategy]['count'] += 1
        strategy_data[strategy]['avg_water_level'] += wl.water_level
        strategy_data[strategy]['avg_flow_rate'] += wl.flow_rate
        if est.accuracy is not None:
            strategy_data[strategy]['avg_accuracy'] += est.accuracy

    for strategy, data in strategy_data.items():
        if data['count'] > 0:
            data['total_estimated'] = round(data['total_estimated'], 2)
            data['total_actual'] = round(data['total_actual'], 2)
            data['avg_accuracy'] = round(data['avg_accuracy'] / data['count'], 2)
            data['avg_water_level'] = round(data['avg_water_level'] / data['count'], 2)
            data['avg_flow_rate'] = round(data['avg_flow_rate'] / data['count'], 2)
            data['efficiency'] = round(data['total_actual'] / data['count'], 2)

    return sorted(strategy_data.values(), key=lambda x: -x['efficiency'])


def simulate_harvest(weir, sim_date, water_level, flow_rate, weather, gate_config, historical_period='all'):
    from datetime import datetime
    if isinstance(sim_date, str):
        sim_date = datetime.strptime(sim_date, '%Y-%m-%d').date()
    today = timezone.now().date()

    date_filter = Q()
    if historical_period == 'recent':
        five_years_ago = today - timedelta(days=365 * 5)
        date_filter = Q(record_date__gte=five_years_ago)
    elif historical_period == 'traditional':
        date_filter = Q(record_date__year__gte=1980, record_date__year__lte=2000)

    similar_records = HarvestRecord.objects.filter(
        date_filter,
        weir=weir,
        record_date__month=sim_date.month,
    )

    similar_with_conditions = []
    for record in similar_records:
        wl = WaterLevel.objects.filter(
            weir=weir,
            record_date=record.record_date,
            is_primary=True
        ).first()

        if not wl:
            continue

        if abs(wl.water_level - water_level) > 0.5:
            continue
        if abs(wl.flow_rate - flow_rate) > 0.3:
            continue

        strategy = get_active_gate_strategy(weir, record.record_date)
        if strategy == gate_config:
            similar_with_conditions.append({
                'weight': record.weight,
                'water_level': wl.water_level,
                'flow_rate': wl.flow_rate,
                'weather': wl.weather,
                'date': record.record_date,
                'strategy': strategy,
            })

    season_factor = get_season_factor(sim_date)
    water_factor = get_water_level_factor(water_level)

    weather_factor_map = {
        '晴': 1.0, '多云': 0.95, '阴': 0.9,
        '小雨': 0.85, '中雨': 0.7, '大雨': 0.5,
        '暴雨': 0.3, '雪': 0.6, '雾': 0.8,
    }
    weather_factor = weather_factor_map.get(weather, 1.0)

    if similar_with_conditions:
        avg_weight = sum(r['weight'] for r in similar_with_conditions) / len(similar_with_conditions)
        base_estimate = avg_weight
        confidence = min(95, 50 + len(similar_with_conditions) * 5)
    else:
        baseline = water_level * 2.0
        base_estimate = baseline
        confidence = 40

    estimated_weight = round(base_estimate * season_factor * water_factor * weather_factor, 2)

    gate_count_open = gate_config.count('开') if gate_config else 0
    gate_efficiency_factor = 1.0 + (gate_count_open * 0.1) if gate_count_open > 0 else 0.5
    estimated_weight = round(estimated_weight * gate_efficiency_factor, 2)

    if estimated_weight >= 15:
        efficiency_level = 'high'
    elif estimated_weight >= 10:
        efficiency_level = 'medium'
    elif estimated_weight >= 5:
        efficiency_level = 'low'
    else:
        efficiency_level = 'very_low'

    influencing_factors = [
        {'factor': '季节', 'effect': f'{season_factor:.2f}x 系数'},
        {'factor': '水位', 'effect': f'{water_factor:.2f}x 系数'},
        {'factor': '天气', 'effect': f'{weather_factor:.2f}x 系数'},
        {'factor': '闸口策略', 'effect': f'{gate_efficiency_factor:.2f}x 系数 (开启{gate_count_open}个)'},
    ]

    return {
        'estimated_weight': estimated_weight,
        'confidence': confidence,
        'similar_records_count': len(similar_with_conditions),
        'similar_records': similar_with_conditions[:10],
        'efficiency_level': efficiency_level,
        'influencing_factors': influencing_factors,
        'factors': {
            'season_factor': season_factor,
            'water_factor': water_factor,
            'weather_factor': weather_factor,
            'gate_efficiency_factor': gate_efficiency_factor,
        },
        'conditions': {
            'water_level': water_level,
            'flow_rate': flow_rate,
            'weather': weather,
            'gate_config': gate_config,
            'season': get_season_name(get_season(sim_date.month)),
            'month': sim_date.month,
        }
    }


def get_monthly_comparison(filters=None):
    filters = filters or {}

    queryset = HarvestEstimate.objects.filter(has_water_data=True)
    queryset = apply_comprehensive_filters(queryset, filters)

    monthly_data = {}
    for est in queryset:
        month = est.estimate_date.month
        month_key = f'{month}月'

        if month_key not in monthly_data:
            monthly_data[month_key] = {
                'month': month_key,
                'month_num': month,
                'total_estimated': 0,
                'total_actual': 0,
                'count': 0,
                'efficiency': 0,
            }

        monthly_data[month_key]['total_estimated'] += est.estimated_weight
        monthly_data[month_key]['total_actual'] += est.actual_weight
        monthly_data[month_key]['count'] += 1

    for month_key, data in monthly_data.items():
        if data['count'] > 0:
            data['total_estimated'] = round(data['total_estimated'], 2)
            data['total_actual'] = round(data['total_actual'], 2)
            data['efficiency'] = round(data['total_actual'] / data['count'], 2)

    return sorted(monthly_data.values(), key=lambda x: x['month_num'])


def get_historical_operation_patterns(weir, start_date=None, end_date=None):
    queryset = GateStatus.objects.filter(weir=weir).order_by('change_time')
    
    if start_date:
        queryset = queryset.filter(change_time__date__gte=start_date)
    if end_date:
        queryset = queryset.filter(change_time__date__lte=end_date)
    
    patterns = {}
    current_gate_status = {}
    
    for gs in queryset:
        current_gate_status[gs.gate_number] = gs.status
        
        date_key = gs.change_time.strftime('%Y-%m')
        if date_key not in patterns:
            patterns[date_key] = {
                'month': date_key,
                'configs': {},
                'total_changes': 0,
            }
        
        config_key = generate_gate_config_key(current_gate_status)
        if config_key not in patterns[date_key]['configs']:
            patterns[date_key]['configs'][config_key] = 0
        patterns[date_key]['configs'][config_key] += 1
        patterns[date_key]['total_changes'] += 1
    
    for date_key, pattern in patterns.items():
        if pattern['total_changes'] > 0:
            for config, count in pattern['configs'].items():
                pattern['configs'][config] = round(count / pattern['total_changes'] * 100, 2)
    
    return sorted(patterns.values(), key=lambda x: x['month'])


def generate_gate_config_key(gate_status_dict):
    parts = []
    for gate_num in sorted(gate_status_dict.keys()):
        status = '开' if gate_status_dict[gate_num] == 'open' else '关'
        parts.append(f'{gate_num}{status}')
    return ', '.join(parts)


def get_typical_gate_configs(weir, season=None, top_n=5):
    queryset = HarvestEstimate.objects.filter(
        weir=weir,
        has_water_data=True,
        gate_strategy__isnull=False
    ).exclude(gate_strategy='')
    
    if season:
        season_months = []
        if season == 'spring':
            season_months = [3, 4, 5]
        elif season == 'summer':
            season_months = [6, 7, 8]
        elif season == 'autumn':
            season_months = [9, 10, 11]
        elif season == 'winter':
            season_months = [12, 1, 2]
        if season_months:
            queryset = queryset.filter(estimate_date__month__in=season_months)
    
    config_counts = {}
    for est in queryset:
        config = est.gate_strategy
        if config not in config_counts:
            config_counts[config] = {
                'config': config,
                'count': 0,
                'total_actual': 0,
                'avg_efficiency': 0,
            }
        config_counts[config]['count'] += 1
        config_counts[config]['total_actual'] += est.actual_weight
    
    for config, data in config_counts.items():
        if data['count'] > 0:
            data['avg_efficiency'] = round(data['total_actual'] / data['count'], 2)
    
    sorted_configs = sorted(config_counts.values(), key=lambda x: -x['count'])
    return sorted_configs[:top_n]


def simulate_multiple_strategies(weir, sim_date, water_level, flow_rate, weather, strategies, historical_period='all'):
    results = []
    
    for strategy in strategies:
        sim_result = simulate_harvest(
            weir=weir,
            sim_date=sim_date,
            water_level=water_level,
            flow_rate=flow_rate,
            weather=weather,
            gate_config=strategy,
            historical_period=historical_period
        )
        sim_result['strategy'] = strategy
        results.append(sim_result)
    
    results.sort(key=lambda x: -x['estimated_weight'])
    
    for i, result in enumerate(results):
        result['rank'] = i + 1
        if i == 0:
            result['advantage'] = 0
        else:
            result['advantage'] = round(results[0]['estimated_weight'] - result['estimated_weight'], 2)
    
    return results


def get_traditional_fishing_calendar(weir):
    season_data = get_seasonal_analysis({'weir': weir})
    
    calendar = []
    for season in season_data:
        calendar.append({
            'season': season['season_name'],
            'season_code': season['season'],
            'avg_efficiency': season['efficiency'],
            'avg_water_level': season['avg_water_level'],
            'avg_flow_rate': season['avg_flow_rate'],
            'recommendation': generate_season_recommendation(season),
        })
    
    return calendar


def generate_season_recommendation(season_data):
    efficiency = season_data['efficiency']
    water_level = season_data['avg_water_level']
    flow_rate = season_data['avg_flow_rate']
    
    recommendations = []
    
    if efficiency >= 15:
        recommendations.append('捕鱼黄金期，建议增加作业频率')
    elif efficiency >= 10:
        recommendations.append('适宜作业，可按常规频率安排')
    elif efficiency >= 5:
        recommendations.append('产量一般，可选择性作业')
    else:
        recommendations.append('产量较低，建议减少作业')
    
    if water_level >= 3:
        recommendations.append('水位较高，注意安全作业')
    elif water_level < 1:
        recommendations.append('水位偏低，可考虑调整闸口策略')
    
    if flow_rate >= 1.5:
        recommendations.append('流速较快，适合顺流捕鱼')
    elif flow_rate < 0.5:
        recommendations.append('流速较慢，可增加闸口开启数量')
    
    return '；'.join(recommendations)


def get_strategy_heatmap_data(filters=None):
    filters = filters or {}
    
    queryset = HarvestEstimate.objects.filter(has_water_data=True)
    queryset = apply_comprehensive_filters(queryset, filters)
    
    water_queryset = WaterLevel.objects.filter(is_primary=True)
    water_queryset = apply_water_level_filters(water_queryset, filters)
    
    water_date_map = {}
    for wl in water_queryset:
        key = (wl.weir_id, wl.record_date)
        water_date_map[key] = wl
    
    water_intervals = [
        (0, 1, '0-1米'),
        (1, 2, '1-2米'),
        (2, 3, '2-3米'),
        (3, 4, '3-4米'),
        (4, 100, '4米以上'),
    ]
    
    seasons = ['spring', 'summer', 'autumn', 'winter']
    season_names = {
        'spring': '春季',
        'summer': '夏季',
        'autumn': '秋季',
        'winter': '冬季',
    }
    
    heatmap_data = []
    for season in seasons:
        for _, _, water_label in water_intervals:
            heatmap_data.append({
                'season': season_names[season],
                'water_level': water_label,
                'efficiency': 0,
                'count': 0,
            })
    
    for est in queryset:
        key = (est.weir_id, est.estimate_date)
        if key not in water_date_map:
            continue
        
        wl = water_date_map[key]
        season = get_season(est.estimate_date.month)
        
        water_label = None
        for min_val, max_val, label in water_intervals:
            if min_val <= wl.water_level < max_val:
                water_label = label
                break
        
        if water_label:
            for cell in heatmap_data:
                if cell['season'] == season_names[season] and cell['water_level'] == water_label:
                    cell['efficiency'] += est.actual_weight
                    cell['count'] += 1
                    break
    
    for cell in heatmap_data:
        if cell['count'] > 0:
            cell['efficiency'] = round(cell['efficiency'] / cell['count'], 2)
    
    return heatmap_data


def get_multi_dimensional_comparison(filters=None):
    filters = filters or {}
    
    seasonal_data = get_seasonal_analysis(filters)
    water_level_data = get_water_level_interval_analysis(filters)
    flow_rate_data = get_flow_rate_analysis(filters)
    weather_data = get_weather_analysis(filters)
    strategy_data = get_strategy_efficiency_comparison(filters)
    
    all_data = []
    
    for d in seasonal_data:
        all_data.append({
            'category': '季节',
            'group': d['season_name'],
            'efficiency': d['efficiency'],
            'count': d['count'],
            'total_actual': d['total_actual'],
        })
    
    for d in water_level_data:
        all_data.append({
            'category': '水位区间',
            'group': d['interval'],
            'efficiency': d['efficiency'],
            'count': d['count'],
            'total_actual': d['total_actual'],
        })
    
    for d in flow_rate_data:
        all_data.append({
            'category': '流速区间',
            'group': d['interval'],
            'efficiency': d['efficiency'],
            'count': d['count'],
            'total_actual': d['total_actual'],
        })
    
    for d in weather_data:
        all_data.append({
            'category': '天气',
            'group': d['weather'],
            'efficiency': d['efficiency'],
            'count': d['count'],
            'total_actual': d['total_actual'],
        })
    
    for d in strategy_data[:5]:
        all_data.append({
            'category': '闸口策略',
            'group': d['strategy'][:20] + '...' if len(d['strategy']) > 20 else d['strategy'],
            'efficiency': d['efficiency'],
            'count': d['count'],
            'total_actual': d['total_actual'],
        })
    
    return all_data


def get_comprehensive_strategy_analysis(filters=None):
    filters = filters or {}
    
    strategy_data = get_strategy_efficiency_comparison(filters)
    
    analysis_result = []
    for strategy in strategy_data:
        strategy_filters = filters.copy()
        strategy_filters['gate_strategy'] = strategy['strategy']
        
        seasonal_breakdown = get_seasonal_analysis(strategy_filters)
        water_breakdown = get_water_level_interval_analysis(strategy_filters)
        
        optimal_conditions = find_optimal_conditions(strategy_filters)
        
        analysis_result.append({
            'strategy': strategy,
            'seasonal_breakdown': seasonal_breakdown,
            'water_breakdown': water_breakdown,
            'optimal_conditions': optimal_conditions,
        })
    
    return analysis_result


def find_optimal_conditions(filters=None):
    filters = filters or {}
    
    seasonal_data = get_seasonal_analysis(filters)
    water_data = get_water_level_interval_analysis(filters)
    flow_data = get_flow_rate_analysis(filters)
    weather_data = get_weather_analysis(filters)
    
    best_season = max(seasonal_data, key=lambda x: x['efficiency']) if seasonal_data else None
    best_water = max(water_data, key=lambda x: x['efficiency']) if water_data else None
    best_flow = max(flow_data, key=lambda x: x['efficiency']) if flow_data else None
    best_weather = max(weather_data, key=lambda x: x['efficiency']) if weather_data else None
    
    return {
        'best_season': best_season,
        'best_water_interval': best_water,
        'best_flow_interval': best_flow,
        'best_weather': best_weather,
    }


def reconstruct_historical_operation(weir, target_date):
    from datetime import datetime
    if isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
    water_level = WaterLevel.objects.filter(
        weir=weir,
        record_date=target_date,
        is_primary=True
    ).first()
    
    gate_strategy = get_active_gate_strategy(weir, target_date)
    
    harvest = HarvestRecord.objects.filter(
        weir=weir,
        record_date=target_date
    ).aggregate(total=Sum('weight'))['total'] or 0
    
    estimate = HarvestEstimate.objects.filter(
        weir=weir,
        estimate_date=target_date
    ).first()
    
    fish_schools = FishSchool.objects.filter(
        weir=weir,
        record_date=target_date
    ).order_by('observe_time')
    
    context = {
        'date': target_date,
        'season': get_season_name(get_season(target_date.month)),
        'water_level': water_level,
        'gate_strategy': gate_strategy,
        'actual_harvest': harvest,
        'estimate': estimate,
        'fish_schools': fish_schools,
    }
    
    if water_level:
        reconstructed = simulate_harvest(
            weir=weir,
            sim_date=target_date,
            water_level=water_level.water_level,
            flow_rate=water_level.flow_rate,
            weather=water_level.weather,
            gate_config=gate_strategy,
            historical_period='all'
        )
        context['reconstructed_estimate'] = reconstructed
        context['reconstruction_accuracy'] = calculate_reconstruction_accuracy(harvest, reconstructed['estimated_weight'])
    
    return context


def calculate_reconstruction_accuracy(actual, estimated):
    if actual <= 0 or estimated <= 0:
        return None
    return round((1 - abs(actual - estimated) / actual) * 100, 2)
