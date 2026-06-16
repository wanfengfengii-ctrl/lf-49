from datetime import datetime, timedelta
from django.db.models import Avg, Sum, Count, Q
from django.utils import timezone
from ..models import Weir, WaterLevel, HarvestRecord, FishSchool, HarvestEstimate, GateStatus
from .harvest_estimator import (
    get_season, get_season_name, apply_water_level_filters, get_active_gate_strategy
)


def apply_gate_filters(queryset, filters, date_field='record_date'):
    has_gate_filter = (
        filters.get('gate_status') or
        filters.get('gate_strategy')
    )
    if not has_gate_filter:
        return queryset

    gate_statuses = GateStatus.objects.all()
    if filters.get('weir'):
        gate_statuses = gate_statuses.filter(weir=filters['weir'])

    gate_date_map = {}
    for gs in gate_statuses:
        key = (gs.weir_id, gs.change_time.date())
        if key not in gate_date_map:
            gate_date_map[key] = {}
        gate_date_map[key][gs.gate_number] = gs.status

    valid_keys = set()
    for (weir_id, record_date), gate_info in gate_date_map.items():
        strategy_parts = []
        for gate_num in sorted(gate_info.keys()):
            status = '开' if gate_info[gate_num] == 'open' else '关'
            strategy_parts.append(f'{gate_num}{status}')
        strategy = ', '.join(strategy_parts)

        if filters.get('gate_strategy'):
            if filters['gate_strategy'] not in strategy:
                continue

        if filters.get('gate_status'):
            gate_status_list = filters['gate_status']
            if isinstance(gate_status_list, str):
                gate_status_list = [gate_status_list]
            has_match = False
            for status in gate_status_list:
                status_text = '开' if status == 'open' else '关'
                if status_text in strategy:
                    has_match = True
                    break
            if not has_match:
                continue

        valid_keys.add((weir_id, record_date))

    if valid_keys:
        q_objects = Q()
        for weir_id, record_date in valid_keys:
            date_filter = {f'{date_field}__gte': record_date, f'{date_field}__lte': record_date}
            q_objects |= Q(weir_id=weir_id, **date_filter)
        queryset = queryset.filter(q_objects)
    else:
        queryset = queryset.none()

    return queryset


def apply_fish_migration_filters(fish_queryset, filters):
    if filters.get('weir'):
        fish_queryset = fish_queryset.filter(weir=filters['weir'])
    if filters.get('start_date'):
        fish_queryset = fish_queryset.filter(record_date__gte=filters['start_date'])
    if filters.get('end_date'):
        fish_queryset = fish_queryset.filter(record_date__lte=filters['end_date'])
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
            fish_queryset = fish_queryset.filter(record_date__month__in=season_months)
    if filters.get('months'):
        fish_queryset = fish_queryset.filter(record_date__month__in=[int(m) for m in filters['months']])
    if filters.get('fish_species'):
        fish_queryset = fish_queryset.filter(fish_type__in=filters['fish_species'])
    has_water_filter = (
        filters.get('water_level_min') is not None or
        filters.get('water_level_max') is not None or
        filters.get('flow_rate_min') is not None or
        filters.get('flow_rate_max') is not None or
        filters.get('weather')
    )
    if has_water_filter:
        water_queryset = WaterLevel.objects.filter(is_primary=True)
        water_queryset = apply_water_level_filters(water_queryset, filters)
        valid_dates = list(water_queryset.values_list('weir_id', 'record_date'))
        if valid_dates:
            q_objects = Q()
            for weir_id, record_date in valid_dates:
                q_objects |= Q(weir_id=weir_id, record_date=record_date)
            fish_queryset = fish_queryset.filter(q_objects)
        else:
            fish_queryset = fish_queryset.none()
    fish_queryset = apply_gate_filters(fish_queryset, filters, 'record_date')
    return fish_queryset


def apply_harvest_filters(harvest_queryset, filters):
    if filters.get('weir'):
        harvest_queryset = harvest_queryset.filter(weir=filters['weir'])
    if filters.get('start_date'):
        harvest_queryset = harvest_queryset.filter(record_date__gte=filters['start_date'])
    if filters.get('end_date'):
        harvest_queryset = harvest_queryset.filter(record_date__lte=filters['end_date'])
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
            harvest_queryset = harvest_queryset.filter(record_date__month__in=season_months)
    if filters.get('months'):
        harvest_queryset = harvest_queryset.filter(record_date__month__in=[int(m) for m in filters['months']])
    if filters.get('fish_species'):
        harvest_queryset = harvest_queryset.filter(fish_species__in=filters['fish_species'])
    has_water_filter = (
        filters.get('water_level_min') is not None or
        filters.get('water_level_max') is not None or
        filters.get('flow_rate_min') is not None or
        filters.get('flow_rate_max') is not None or
        filters.get('weather')
    )
    if has_water_filter:
        water_queryset = WaterLevel.objects.filter(is_primary=True)
        water_queryset = apply_water_level_filters(water_queryset, filters)
        valid_dates = list(water_queryset.values_list('weir_id', 'record_date'))
        if valid_dates:
            q_objects = Q()
            for weir_id, record_date in valid_dates:
                q_objects |= Q(weir_id=weir_id, record_date=record_date)
            harvest_queryset = harvest_queryset.filter(q_objects)
        else:
            harvest_queryset = harvest_queryset.none()
    harvest_queryset = apply_gate_filters(harvest_queryset, filters, 'record_date')
    return harvest_queryset


def get_available_fish_species():
    from_schools = list(
        FishSchool.objects.values_list('fish_type', flat=True).distinct()
    )
    from_harvests = list(
        HarvestRecord.objects.values_list('fish_species', flat=True).distinct()
    )
    all_species = list(set(from_schools + from_harvests))
    return sorted([s for s in all_species if s])


def get_fish_school_summary(filters=None):
    filters = filters or {}
    queryset = FishSchool.objects.all()
    queryset = apply_fish_migration_filters(queryset, filters)

    total_count = queryset.aggregate(total=Sum('estimated_count'))['total'] or 0
    record_count = queryset.count()
    weir_count = queryset.values('weir').distinct().count()
    species_count = queryset.values('fish_type').distinct().count()

    direction_stats = {}
    for fs in queryset:
        direction = fs.direction
        if direction not in direction_stats:
            direction_stats[direction] = {
                'direction': direction,
                'direction_name': '逆流而上' if direction == 'upstream' else '顺流而下',
                'count': 0,
                'total_estimated': 0,
            }
        direction_stats[direction]['count'] += 1
        direction_stats[direction]['total_estimated'] += fs.estimated_count

    for d in direction_stats.values():
        d['total_estimated'] = round(d['total_estimated'], 2)

    return {
        'total_fish_count': total_count,
        'school_record_count': record_count,
        'weir_count': weir_count,
        'species_count': species_count,
        'direction_stats': list(direction_stats.values()),
    }


def get_harvest_summary(filters=None):
    filters = filters or {}
    queryset = HarvestRecord.objects.all()
    queryset = apply_harvest_filters(queryset, filters)

    total_weight = queryset.aggregate(total=Sum('weight'))['total'] or 0
    total_quantity = queryset.aggregate(total=Sum('quantity'))['total'] or 0
    record_count = queryset.count()
    species_count = queryset.values('fish_species').distinct().count()

    return {
        'total_weight': round(total_weight, 2),
        'total_quantity': total_quantity,
        'harvest_record_count': record_count,
        'species_count': species_count,
    }


def get_monthly_migration_trend(filters=None):
    filters = filters or {}
    fish_queryset = FishSchool.objects.all()
    fish_queryset = apply_fish_migration_filters(fish_queryset, filters)

    harvest_queryset = HarvestRecord.objects.all()
    harvest_queryset = apply_harvest_filters(harvest_queryset, filters)

    monthly_data = {}

    for fs in fish_queryset:
        month_key = fs.record_date.strftime('%Y-%m')
        if month_key not in monthly_data:
            monthly_data[month_key] = {
                'month': month_key,
                'month_num': fs.record_date.month,
                'fish_school_count': 0,
                'total_fish_estimated': 0,
                'harvest_weight': 0,
                'harvest_quantity': 0,
                'harvest_count': 0,
            }
        monthly_data[month_key]['fish_school_count'] += 1
        monthly_data[month_key]['total_fish_estimated'] += fs.estimated_count

    for hr in harvest_queryset:
        month_key = hr.record_date.strftime('%Y-%m')
        if month_key not in monthly_data:
            monthly_data[month_key] = {
                'month': month_key,
                'month_num': hr.record_date.month,
                'fish_school_count': 0,
                'total_fish_estimated': 0,
                'harvest_weight': 0,
                'harvest_quantity': 0,
                'harvest_count': 0,
            }
        monthly_data[month_key]['harvest_weight'] += hr.weight
        monthly_data[month_key]['harvest_quantity'] += hr.quantity
        monthly_data[month_key]['harvest_count'] += 1

    result = []
    for month_key in sorted(monthly_data.keys()):
        d = monthly_data[month_key]
        d['total_fish_estimated'] = round(d['total_fish_estimated'], 2)
        d['harvest_weight'] = round(d['harvest_weight'], 2)
        if d['total_fish_estimated'] > 0:
            d['conversion_rate'] = round(d['harvest_weight'] / d['total_fish_estimated'] * 100, 2)
        else:
            d['conversion_rate'] = 0
        result.append(d)

    return result


def get_seasonal_migration_analysis(filters=None):
    filters = filters or {}
    fish_queryset = FishSchool.objects.all()
    fish_queryset = apply_fish_migration_filters(fish_queryset, filters)

    harvest_queryset = HarvestRecord.objects.all()
    harvest_queryset = apply_harvest_filters(harvest_queryset, filters)

    water_queryset = WaterLevel.objects.filter(is_primary=True)
    water_queryset = apply_water_level_filters(water_queryset, filters)

    water_date_map = {}
    for wl in water_queryset:
        key = (wl.weir_id, wl.record_date)
        water_date_map[key] = wl

    seasonal_data = {}
    season_names = {
        'spring': '春季', 'summer': '夏季',
        'autumn': '秋季', 'winter': '冬季',
    }

    for season in ['spring', 'summer', 'autumn', 'winter']:
        seasonal_data[season] = {
            'season': season,
            'season_name': season_names[season],
            'fish_school_count': 0,
            'total_fish_estimated': 0,
            'harvest_weight': 0,
            'harvest_quantity': 0,
            'harvest_count': 0,
            'avg_water_level': 0,
            'avg_flow_rate': 0,
            'water_record_count': 0,
        }

    for fs in fish_queryset:
        season = get_season(fs.record_date.month)
        if season in seasonal_data:
            seasonal_data[season]['fish_school_count'] += 1
            seasonal_data[season]['total_fish_estimated'] += fs.estimated_count

    for hr in harvest_queryset:
        season = get_season(hr.record_date.month)
        if season in seasonal_data:
            seasonal_data[season]['harvest_weight'] += hr.weight
            seasonal_data[season]['harvest_quantity'] += hr.quantity
            seasonal_data[season]['harvest_count'] += 1

    for wl in water_queryset:
        season = get_season(wl.record_date.month)
        if season in seasonal_data:
            seasonal_data[season]['avg_water_level'] += wl.water_level
            seasonal_data[season]['avg_flow_rate'] += wl.flow_rate
            seasonal_data[season]['water_record_count'] += 1

    for season, data in seasonal_data.items():
        if data['water_record_count'] > 0:
            data['avg_water_level'] = round(data['avg_water_level'] / data['water_record_count'], 2)
            data['avg_flow_rate'] = round(data['avg_flow_rate'] / data['water_record_count'], 2)
        data['total_fish_estimated'] = round(data['total_fish_estimated'], 2)
        data['harvest_weight'] = round(data['harvest_weight'], 2)
        if data['total_fish_estimated'] > 0:
            data['conversion_rate'] = round(data['harvest_weight'] / data['total_fish_estimated'] * 100, 2)
        else:
            data['conversion_rate'] = 0
        if data['fish_school_count'] > 0:
            data['avg_school_size'] = round(data['total_fish_estimated'] / data['fish_school_count'], 2)
        else:
            data['avg_school_size'] = 0

    season_order = ['spring', 'summer', 'autumn', 'winter']
    return [seasonal_data[s] for s in season_order]


def get_water_level_migration_analysis(filters=None):
    filters = filters or {}
    fish_queryset = FishSchool.objects.all()
    fish_queryset = apply_fish_migration_filters(fish_queryset, filters)

    harvest_queryset = HarvestRecord.objects.all()
    harvest_queryset = apply_harvest_filters(harvest_queryset, filters)

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
            'fish_school_count': 0,
            'total_fish_estimated': 0,
            'harvest_weight': 0,
            'harvest_quantity': 0,
            'harvest_count': 0,
        }

    for fs in fish_queryset:
        key = (fs.weir_id, fs.record_date)
        if key in water_date_map:
            wl = water_date_map[key]
            for min_val, max_val, label in intervals:
                if min_val <= wl.water_level < max_val:
                    interval_data[label]['fish_school_count'] += 1
                    interval_data[label]['total_fish_estimated'] += fs.estimated_count
                    break

    for hr in harvest_queryset:
        key = (hr.weir_id, hr.record_date)
        if key in water_date_map:
            wl = water_date_map[key]
            for min_val, max_val, label in intervals:
                if min_val <= wl.water_level < max_val:
                    interval_data[label]['harvest_weight'] += hr.weight
                    interval_data[label]['harvest_quantity'] += hr.quantity
                    interval_data[label]['harvest_count'] += 1
                    break

    for label, data in interval_data.items():
        data['total_fish_estimated'] = round(data['total_fish_estimated'], 2)
        data['harvest_weight'] = round(data['harvest_weight'], 2)
        if data['total_fish_estimated'] > 0:
            data['conversion_rate'] = round(data['harvest_weight'] / data['total_fish_estimated'] * 100, 2)
        else:
            data['conversion_rate'] = 0
        if data['fish_school_count'] > 0:
            data['avg_school_size'] = round(data['total_fish_estimated'] / data['fish_school_count'], 2)
        else:
            data['avg_school_size'] = 0

    return [interval_data[label] for _, _, label in intervals]


def get_weather_migration_analysis(filters=None):
    filters = filters or {}
    fish_queryset = FishSchool.objects.all()
    fish_queryset = apply_fish_migration_filters(fish_queryset, filters)

    harvest_queryset = HarvestRecord.objects.all()
    harvest_queryset = apply_harvest_filters(harvest_queryset, filters)

    water_queryset = WaterLevel.objects.filter(is_primary=True)
    water_queryset = apply_water_level_filters(water_queryset, filters)

    water_date_map = {}
    for wl in water_queryset:
        key = (wl.weir_id, wl.record_date)
        water_date_map[key] = wl

    weather_data = {}

    for fs in fish_queryset:
        key = (fs.weir_id, fs.record_date)
        if key in water_date_map:
            wl = water_date_map[key]
            weather = wl.weather
            if weather not in weather_data:
                weather_data[weather] = {
                    'weather': weather,
                    'fish_school_count': 0,
                    'total_fish_estimated': 0,
                    'harvest_weight': 0,
                    'harvest_quantity': 0,
                    'harvest_count': 0,
                }
            weather_data[weather]['fish_school_count'] += 1
            weather_data[weather]['total_fish_estimated'] += fs.estimated_count

    for hr in harvest_queryset:
        key = (hr.weir_id, hr.record_date)
        if key in water_date_map:
            wl = water_date_map[key]
            weather = wl.weather
            if weather not in weather_data:
                weather_data[weather] = {
                    'weather': weather,
                    'fish_school_count': 0,
                    'total_fish_estimated': 0,
                    'harvest_weight': 0,
                    'harvest_quantity': 0,
                    'harvest_count': 0,
                }
            weather_data[weather]['harvest_weight'] += hr.weight
            weather_data[weather]['harvest_quantity'] += hr.quantity
            weather_data[weather]['harvest_count'] += 1

    for weather, data in weather_data.items():
        data['total_fish_estimated'] = round(data['total_fish_estimated'], 2)
        data['harvest_weight'] = round(data['harvest_weight'], 2)
        if data['total_fish_estimated'] > 0:
            data['conversion_rate'] = round(data['harvest_weight'] / data['total_fish_estimated'] * 100, 2)
        else:
            data['conversion_rate'] = 0
        if data['fish_school_count'] > 0:
            data['avg_school_size'] = round(data['total_fish_estimated'] / data['fish_school_count'], 2)
        else:
            data['avg_school_size'] = 0

    return sorted(weather_data.values(), key=lambda x: -x['harvest_weight'])


def get_species_migration_analysis(filters=None):
    filters = filters or {}
    fish_queryset = FishSchool.objects.all()
    fish_queryset = apply_fish_migration_filters(fish_queryset, filters)

    harvest_queryset = HarvestRecord.objects.all()
    harvest_queryset = apply_harvest_filters(harvest_queryset, filters)

    species_data = {}

    for fs in fish_queryset:
        species = fs.fish_type
        if species not in species_data:
            species_data[species] = {
                'species': species,
                'fish_school_count': 0,
                'total_fish_estimated': 0,
                'harvest_weight': 0,
                'harvest_quantity': 0,
                'harvest_count': 0,
                'upstream_count': 0,
                'downstream_count': 0,
            }
        species_data[species]['fish_school_count'] += 1
        species_data[species]['total_fish_estimated'] += fs.estimated_count
        if fs.direction == 'upstream':
            species_data[species]['upstream_count'] += 1
        else:
            species_data[species]['downstream_count'] += 1

    for hr in harvest_queryset:
        species = hr.fish_species
        if species not in species_data:
            species_data[species] = {
                'species': species,
                'fish_school_count': 0,
                'total_fish_estimated': 0,
                'harvest_weight': 0,
                'harvest_quantity': 0,
                'harvest_count': 0,
                'upstream_count': 0,
                'downstream_count': 0,
            }
        species_data[species]['harvest_weight'] += hr.weight
        species_data[species]['harvest_quantity'] += hr.quantity
        species_data[species]['harvest_count'] += 1

    for species, data in species_data.items():
        data['total_fish_estimated'] = round(data['total_fish_estimated'], 2)
        data['harvest_weight'] = round(data['harvest_weight'], 2)
        if data['total_fish_estimated'] > 0:
            data['conversion_rate'] = round(data['harvest_weight'] / data['total_fish_estimated'] * 100, 2)
        else:
            data['conversion_rate'] = 0
        if data['fish_school_count'] > 0:
            data['avg_school_size'] = round(data['total_fish_estimated'] / data['fish_school_count'], 2)
        else:
            data['avg_school_size'] = 0

    return sorted(species_data.values(), key=lambda x: -x['harvest_weight'])


def calculate_correlation_analysis(filters=None):
    filters = filters or {}
    fish_queryset = FishSchool.objects.all()
    fish_queryset = apply_fish_migration_filters(fish_queryset, filters)

    harvest_queryset = HarvestRecord.objects.all()
    harvest_queryset = apply_harvest_filters(harvest_queryset, filters)

    water_queryset = WaterLevel.objects.filter(is_primary=True)
    water_queryset = apply_water_level_filters(water_queryset, filters)

    daily_data = {}

    for fs in fish_queryset:
        key = (fs.weir_id, fs.record_date)
        if key not in daily_data:
            daily_data[key] = {
                'fish_estimated': 0,
                'harvest_weight': 0,
                'water_level': None,
                'flow_rate': None,
                'weather': None,
            }
        daily_data[key]['fish_estimated'] += fs.estimated_count

    for hr in harvest_queryset:
        key = (hr.weir_id, hr.record_date)
        if key not in daily_data:
            daily_data[key] = {
                'fish_estimated': 0,
                'harvest_weight': 0,
                'water_level': None,
                'flow_rate': None,
                'weather': None,
            }
        daily_data[key]['harvest_weight'] += hr.weight

    for wl in water_queryset:
        key = (wl.weir_id, wl.record_date)
        if key in daily_data:
            daily_data[key]['water_level'] = wl.water_level
            daily_data[key]['flow_rate'] = wl.flow_rate
            daily_data[key]['weather'] = wl.weather

    valid_days = [d for d in daily_data.values()
                  if d['fish_estimated'] > 0 and d['harvest_weight'] > 0]

    if len(valid_days) < 2:
        return {
            'fish_harvest_correlation': None,
            'water_level_fish_correlation': None,
            'flow_rate_fish_correlation': None,
            'water_level_harvest_correlation': None,
            'flow_rate_harvest_correlation': None,
            'valid_day_count': len(valid_days),
        }

    n = len(valid_days)

    def pearson_correlation(x_list, y_list):
        if len(x_list) < 2 or len(y_list) < 2:
            return None
        n_pairs = min(len(x_list), len(y_list))
        if n_pairs < 2:
            return None
        mean_x = sum(x_list) / n_pairs
        mean_y = sum(y_list) / n_pairs
        numerator = sum((x_list[i] - mean_x) * (y_list[i] - mean_y) for i in range(n_pairs))
        denominator_x = sum((x - mean_x) ** 2 for x in x_list) ** 0.5
        denominator_y = sum((y - mean_y) ** 2 for y in y_list) ** 0.5
        if denominator_x == 0 or denominator_y == 0:
            return None
        return round(numerator / (denominator_x * denominator_y), 4)

    fish_counts = [d['fish_estimated'] for d in valid_days]
    harvest_weights = [d['harvest_weight'] for d in valid_days]
    water_levels = [d['water_level'] for d in valid_days if d['water_level'] is not None]
    flow_rates = [d['flow_rate'] for d in valid_days if d['flow_rate'] is not None]

    valid_water_days = [d for d in valid_days if d['water_level'] is not None]
    wl_fish = [d['fish_estimated'] for d in valid_water_days]
    wl_harvest = [d['harvest_weight'] for d in valid_water_days]
    wl_values = [d['water_level'] for d in valid_water_days]

    valid_flow_days = [d for d in valid_days if d['flow_rate'] is not None]
    fr_fish = [d['fish_estimated'] for d in valid_flow_days]
    fr_harvest = [d['harvest_weight'] for d in valid_flow_days]
    fr_values = [d['flow_rate'] for d in valid_flow_days]

    return {
        'fish_harvest_correlation': pearson_correlation(fish_counts, harvest_weights),
        'water_level_fish_correlation': pearson_correlation(wl_values, wl_fish),
        'flow_rate_fish_correlation': pearson_correlation(fr_values, fr_fish),
        'water_level_harvest_correlation': pearson_correlation(wl_values, wl_harvest),
        'flow_rate_harvest_correlation': pearson_correlation(fr_values, fr_harvest),
        'valid_day_count': len(valid_days),
    }


def get_key_factor_ranking(filters=None):
    filters = filters or {}
    correlations = calculate_correlation_analysis(filters)
    seasonal_data = get_seasonal_migration_analysis(filters)
    water_data = get_water_level_migration_analysis(filters)
    weather_data = get_weather_migration_analysis(filters)

    factors = []

    if correlations['fish_harvest_correlation'] is not None:
        factors.append({
            'factor': '鱼群数量-收获量关联',
            'category': '生态关联',
            'score': round(abs(correlations['fish_harvest_correlation']) * 100, 2),
            'correlation': correlations['fish_harvest_correlation'],
            'description': '鱼群经过数量与实际收获量的相关性强度',
            'interpretation': interpret_correlation(correlations['fish_harvest_correlation']),
        })

    if correlations['water_level_fish_correlation'] is not None:
        factors.append({
            'factor': '水位-鱼群数量关联',
            'category': '水文因子',
            'score': round(abs(correlations['water_level_fish_correlation']) * 100, 2),
            'correlation': correlations['water_level_fish_correlation'],
            'description': '水位高度对鱼群经过数量的影响程度',
            'interpretation': interpret_correlation(correlations['water_level_fish_correlation']),
        })

    if correlations['flow_rate_fish_correlation'] is not None:
        factors.append({
            'factor': '流速-鱼群数量关联',
            'category': '水文因子',
            'score': round(abs(correlations['flow_rate_fish_correlation']) * 100, 2),
            'correlation': correlations['flow_rate_fish_correlation'],
            'description': '水流速度对鱼群经过数量的影响程度',
            'interpretation': interpret_correlation(correlations['flow_rate_fish_correlation']),
        })

    if correlations['water_level_harvest_correlation'] is not None:
        factors.append({
            'factor': '水位-收获量关联',
            'category': '水文因子',
            'score': round(abs(correlations['water_level_harvest_correlation']) * 100, 2),
            'correlation': correlations['water_level_harvest_correlation'],
            'description': '水位高度对实际收获量的影响程度',
            'interpretation': interpret_correlation(correlations['water_level_harvest_correlation']),
        })

    if correlations['flow_rate_harvest_correlation'] is not None:
        factors.append({
            'factor': '流速-收获量关联',
            'category': '水文因子',
            'score': round(abs(correlations['flow_rate_harvest_correlation']) * 100, 2),
            'correlation': correlations['flow_rate_harvest_correlation'],
            'description': '水流速度对实际收获量的影响程度',
            'interpretation': interpret_correlation(correlations['flow_rate_harvest_correlation']),
        })

    if seasonal_data:
        best_season = max(seasonal_data, key=lambda x: x['conversion_rate'])
        if best_season['fish_school_count'] > 0:
            factors.append({
                'factor': f'最佳季节: {best_season["season_name"]}',
                'category': '季节因子',
                'score': round(best_season['conversion_rate'], 2),
                'correlation': None,
                'description': f'{best_season["season_name"]}鱼群捕获转化率最高',
                'interpretation': f'转化率 {best_season["conversion_rate"]}%，鱼群记录 {best_season["fish_school_count"]} 次',
            })

    if water_data:
        valid_water = [w for w in water_data if w['fish_school_count'] > 0]
        if valid_water:
            best_water = max(valid_water, key=lambda x: x['conversion_rate'])
            factors.append({
                'factor': f'最佳水位区间: {best_water["interval"]}',
                'category': '水文因子',
                'score': round(best_water['conversion_rate'], 2),
                'correlation': None,
                'description': f'{best_water["interval"]}水位区间鱼群捕获转化率最高',
                'interpretation': f'转化率 {best_water["conversion_rate"]}%，鱼群记录 {best_water["fish_school_count"]} 次',
            })

    if weather_data:
        valid_weather = [w for w in weather_data if w['fish_school_count'] > 0]
        if valid_weather:
            best_weather = max(valid_weather, key=lambda x: x['conversion_rate'])
            factors.append({
                'factor': f'最佳天气: {best_weather["weather"]}',
                'category': '天气因子',
                'score': round(best_weather['conversion_rate'], 2),
                'correlation': None,
                'description': f'{best_weather["weather"]}天气下鱼群捕获转化率最高',
                'interpretation': f'转化率 {best_weather["conversion_rate"]}%，鱼群记录 {best_weather["fish_school_count"]} 次',
            })

    return sorted(factors, key=lambda x: -x['score'])


def interpret_correlation(corr):
    if corr is None:
        return '数据不足，无法判断'
    abs_corr = abs(corr)
    direction = '正相关' if corr > 0 else '负相关'
    if abs_corr >= 0.8:
        return f'极强{direction}'
    elif abs_corr >= 0.6:
        return f'强{direction}'
    elif abs_corr >= 0.4:
        return f'中等{direction}'
    elif abs_corr >= 0.2:
        return f'弱{direction}'
    else:
        return '几乎无相关性'


def generate_migration_warnings(filters=None):
    filters = filters or {}
    warnings = []

    today = timezone.now().date()
    current_month = today.month
    current_season = get_season(current_month)

    seasonal_data = get_seasonal_migration_analysis(filters)
    monthly_trend = get_monthly_migration_trend(filters)

    if seasonal_data:
        current_season_data = next(
            (s for s in seasonal_data if s['season'] == current_season), None
        )
        best_season = max(seasonal_data, key=lambda x: x['fish_school_count'])

        if current_season_data and best_season:
            if current_season_data['season'] == best_season['season']:
                warnings.append({
                    'level': 'success',
                    'type': '鱼汛活跃期',
                    'icon': '🐟',
                    'title': f'当前正值{current_season_data["season_name"]}鱼汛活跃期',
                    'message': f'历史数据显示{best_season["season_name"]}是鱼群经过最频繁的季节，'
                               f'共记录{best_season["fish_school_count"]}次鱼群经过，'
                               f'预估总数量{best_season["total_fish_estimated"]}尾。'
                               f'建议加强观测，把握捕鱼时机。',
                })
            elif current_season_data['fish_school_count'] < best_season['fish_school_count'] * 0.5:
                warnings.append({
                    'level': 'warning',
                    'type': '鱼汛低谷期',
                    'icon': '📉',
                    'title': f'当前处于{current_season_data["season_name"]}，鱼群活动相对较少',
                    'message': f'建议等待{best_season["season_name"]}鱼汛高峰期到来，'
                               f'或调整闸口策略以适应当前水情。',
                })

    recent_months = monthly_trend[-3:] if len(monthly_trend) >= 3 else monthly_trend
    if len(recent_months) >= 2:
        avg_fish = sum(m['total_fish_estimated'] for m in recent_months) / len(recent_months)
        latest = recent_months[-1]
        if avg_fish > 0 and latest['total_fish_estimated'] > avg_fish * 1.5:
            warnings.append({
                'level': 'warning',
                'type': '鱼群异常活跃',
                'icon': '⚠️',
                'title': f'{latest["month"]}月鱼群经过数量异常增加',
                'message': f'近3月平均鱼群预估数量为{round(avg_fish, 2)}尾，'
                           f'{latest["month"]}月达到{latest["total_fish_estimated"]}尾，'
                           f'超过平均值{round(latest["total_fish_estimated"] / avg_fish * 100 - 100, 1)}%。'
                           f'可能存在特殊鱼汛，建议密切关注。',
            })

    correlations = calculate_correlation_analysis(filters)
    if correlations['fish_harvest_correlation'] is not None:
        if abs(correlations['fish_harvest_correlation']) < 0.3:
            warnings.append({
                'level': 'info',
                'type': '关联度提示',
                'icon': '💡',
                'title': '鱼群经过数量与收获量关联度较低',
                'message': f'当前相关系数为{correlations["fish_harvest_correlation"]}，'
                           f'说明鱼群经过不一定能转化为收获。'
                           f'建议优化闸口策略和作业时机，提高捕获转化率。',
            })

    water_data = get_water_level_migration_analysis(filters)
    valid_water = [w for w in water_data if w['fish_school_count'] > 0]
    if valid_water:
        best_water = max(valid_water, key=lambda x: x['avg_school_size'])
        if best_water['avg_school_size'] > 0:
            warnings.append({
                'level': 'info',
                'type': '水位建议',
                'icon': '💧',
                'title': f'水位{best_water["interval"]}时鱼群规模最大',
                'message': f'历史数据显示，当水位处于{best_water["interval"]}时，'
                           f'平均鱼群规模达{best_water["avg_school_size"]}尾，'
                           f'捕获转化率{best_water["conversion_rate"]}%。',
            })

    if not warnings:
        warnings.append({
            'level': 'info',
            'type': '常规状态',
            'icon': '✅',
            'title': '当前无特殊预警',
            'message': '系统运行正常，请继续保持数据记录以获得更准确的分析结果。',
        })

    return warnings


def get_species_migration_path_analysis(filters=None):
    filters = filters or {}
    fish_queryset = FishSchool.objects.all()
    fish_queryset = apply_fish_migration_filters(fish_queryset, filters)

    harvest_queryset = HarvestRecord.objects.all()
    harvest_queryset = apply_harvest_filters(harvest_queryset, filters)

    water_queryset = WaterLevel.objects.filter(is_primary=True)
    water_queryset = apply_water_level_filters(water_queryset, filters)

    water_date_map = {}
    for wl in water_queryset:
        key = (wl.weir_id, wl.record_date)
        water_date_map[key] = wl

    gate_date_map = {}
    gate_statuses = GateStatus.objects.all()
    if filters.get('weir'):
        gate_statuses = gate_statuses.filter(weir=filters['weir'])
    for gs in gate_statuses:
        key = (gs.weir_id, gs.change_time.date())
        if key not in gate_date_map:
            gate_date_map[key] = {}
        gate_date_map[key][gs.gate_number] = gs.status

    season_names = {
        'spring': '春季', 'summer': '夏季',
        'autumn': '秋季', 'winter': '冬季',
    }

    water_intervals = [
        (0, 1, '0-1米'), (1, 2, '1-2米'), (2, 3, '2-3米'),
        (3, 4, '3-4米'), (4, 100, '4米以上'),
    ]

    flow_intervals = [
        (0, 0.5, '0-0.5 m/s'), (0.5, 1, '0.5-1 m/s'),
        (1, 1.5, '1-1.5 m/s'), (1.5, 2, '1.5-2 m/s'),
        (2, 100, '2 m/s以上'),
    ]

    species_path_data = {}

    for fs in fish_queryset:
        species = fs.fish_type
        if species not in species_path_data:
            species_path_data[species] = {
                'species': species,
                'total_fish_estimated': 0,
                'fish_school_count': 0,
                'upstream_count': 0,
                'downstream_count': 0,
                'seasonal_distribution': {'spring': 0, 'summer': 0, 'autumn': 0, 'winter': 0},
                'water_level_distribution': {label: 0 for _, _, label in water_intervals},
                'flow_rate_distribution': {label: 0 for _, _, label in flow_intervals},
                'weather_distribution': {},
                'gate_status_distribution': {'open': 0, 'closed': 0},
                'gate_strategy_occurrences': {},
                'avg_school_size': 0,
            }

        species_path_data[species]['total_fish_estimated'] += fs.estimated_count
        species_path_data[species]['fish_school_count'] += 1

        if fs.direction == 'upstream':
            species_path_data[species]['upstream_count'] += 1
        else:
            species_path_data[species]['downstream_count'] += 1

        season = get_season(fs.record_date.month)
        species_path_data[species]['seasonal_distribution'][season] += fs.estimated_count

        wl_key = (fs.weir_id, fs.record_date)
        if wl_key in water_date_map:
            wl = water_date_map[wl_key]
            for min_val, max_val, label in water_intervals:
                if min_val <= wl.water_level < max_val:
                    species_path_data[species]['water_level_distribution'][label] += fs.estimated_count
                    break
            for min_val, max_val, label in flow_intervals:
                if min_val <= wl.flow_rate < max_val:
                    species_path_data[species]['flow_rate_distribution'][label] += fs.estimated_count
                    break
            weather = wl.weather
            if weather not in species_path_data[species]['weather_distribution']:
                species_path_data[species]['weather_distribution'][weather] = 0
            species_path_data[species]['weather_distribution'][weather] += fs.estimated_count

        gate_key = (fs.weir_id, fs.record_date)
        if gate_key in gate_date_map:
            gate_info = gate_date_map[gate_key]
            strategy_parts = []
            open_count = 0
            closed_count = 0
            for gate_num in sorted(gate_info.keys()):
                status = gate_info[gate_num]
                status_text = '开' if status == 'open' else '关'
                strategy_parts.append(f'{gate_num}{status_text}')
                if status == 'open':
                    open_count += 1
                else:
                    closed_count += 1
            strategy = ', '.join(strategy_parts)
            if strategy not in species_path_data[species]['gate_strategy_occurrences']:
                species_path_data[species]['gate_strategy_occurrences'][strategy] = {
                    'count': 0,
                    'total_fish': 0,
                }
            species_path_data[species]['gate_strategy_occurrences'][strategy]['count'] += 1
            species_path_data[species]['gate_strategy_occurrences'][strategy]['total_fish'] += fs.estimated_count

            if open_count > 0:
                species_path_data[species]['gate_status_distribution']['open'] += fs.estimated_count
            if closed_count > 0:
                species_path_data[species]['gate_status_distribution']['closed'] += fs.estimated_count

    for hr in harvest_queryset:
        species = hr.fish_species
        if species not in species_path_data:
            species_path_data[species] = {
                'species': species,
                'total_fish_estimated': 0,
                'fish_school_count': 0,
                'upstream_count': 0,
                'downstream_count': 0,
                'seasonal_distribution': {'spring': 0, 'summer': 0, 'autumn': 0, 'winter': 0},
                'water_level_distribution': {label: 0 for _, _, label in water_intervals},
                'flow_rate_distribution': {label: 0 for _, _, label in flow_intervals},
                'weather_distribution': {},
                'gate_status_distribution': {'open': 0, 'closed': 0},
                'gate_strategy_occurrences': {},
                'avg_school_size': 0,
                'total_harvest_weight': 0,
                'total_harvest_quantity': 0,
            }
        if 'total_harvest_weight' not in species_path_data[species]:
            species_path_data[species]['total_harvest_weight'] = 0
            species_path_data[species]['total_harvest_quantity'] = 0
        species_path_data[species]['total_harvest_weight'] += hr.weight
        species_path_data[species]['total_harvest_quantity'] += hr.quantity

    for species, data in species_path_data.items():
        if data['fish_school_count'] > 0:
            data['avg_school_size'] = round(data['total_fish_estimated'] / data['fish_school_count'], 2)
        data['total_fish_estimated'] = round(data['total_fish_estimated'], 2)
        if 'total_harvest_weight' in data:
            data['total_harvest_weight'] = round(data['total_harvest_weight'], 2)
        if data.get('total_fish_estimated', 0) > 0 and data.get('total_harvest_weight', 0) > 0:
            data['conversion_rate'] = round(data['total_harvest_weight'] / data['total_fish_estimated'] * 100, 2)
        else:
            data['conversion_rate'] = 0

        top_strategies = sorted(
            data['gate_strategy_occurrences'].items(),
            key=lambda x: -x[1]['total_fish']
        )[:5]
        data['top_gate_strategies'] = [
            {
                'strategy': s,
                'count': d['count'],
                'total_fish': round(d['total_fish'], 2),
                'avg_fish_per_occurrence': round(d['total_fish'] / d['count'], 2) if d['count'] > 0 else 0,
            }
            for s, d in top_strategies
        ]

    result = sorted(species_path_data.values(), key=lambda x: -x.get('total_harvest_weight', 0))

    return result


def get_species_response_comparison(filters=None):
    filters = filters or {}
    path_analysis = get_species_migration_path_analysis(filters)

    season_names = {
        'spring': '春季', 'summer': '夏季',
        'autumn': '秋季', 'winter': '冬季',
    }

    comparison_data = []
    species_list = [d['species'] for d in path_analysis[:8]]

    for season_code, season_name in season_names.items():
        season_data = {
            'group': season_name,
            'group_type': 'season',
            'species_values': {},
        }
        for data in path_analysis:
            if data['species'] in species_list:
                season_data['species_values'][data['species']] = data['seasonal_distribution'].get(season_code, 0)
        comparison_data.append(season_data)

    water_labels = ['0-1米', '1-2米', '2-3米', '3-4米', '4米以上']
    for label in water_labels:
        water_data = {
            'group': f'水位 {label}',
            'group_type': 'water_level',
            'species_values': {},
        }
        for data in path_analysis:
            if data['species'] in species_list:
                water_data['species_values'][data['species']] = data['water_level_distribution'].get(label, 0)
        comparison_data.append(water_data)

    flow_labels = ['0-0.5 m/s', '0.5-1 m/s', '1-1.5 m/s', '1.5-2 m/s', '2 m/s以上']
    for label in flow_labels:
        flow_data = {
            'group': f'流速 {label}',
            'group_type': 'flow_rate',
            'species_values': {},
        }
        for data in path_analysis:
            if data['species'] in species_list:
                flow_data['species_values'][data['species']] = data['flow_rate_distribution'].get(label, 0)
        comparison_data.append(flow_data)

    gate_status_map = {'open': '闸口开启', 'closed': '闸口关闭'}
    for status_code, status_name in gate_status_map.items():
        gate_data = {
            'group': status_name,
            'group_type': 'gate_status',
            'species_values': {},
        }
        for data in path_analysis:
            if data['species'] in species_list:
                gate_data['species_values'][data['species']] = data['gate_status_distribution'].get(status_code, 0)
        comparison_data.append(gate_data)

    return {
        'species_list': species_list,
        'comparison_data': comparison_data,
    }


def get_gate_synergy_analysis(filters=None):
    filters = filters or {}
    fish_queryset = FishSchool.objects.all()
    fish_queryset = apply_fish_migration_filters(fish_queryset, filters)

    harvest_queryset = HarvestRecord.objects.all()
    harvest_queryset = apply_harvest_filters(harvest_queryset, filters)

    water_queryset = WaterLevel.objects.filter(is_primary=True)
    water_queryset = apply_water_level_filters(water_queryset, filters)

    water_date_map = {}
    for wl in water_queryset:
        key = (wl.weir_id, wl.record_date)
        water_date_map[key] = wl

    gate_statuses = GateStatus.objects.all()
    if filters.get('weir'):
        gate_statuses = gate_statuses.filter(weir=filters['weir'])

    gate_date_map = {}
    for gs in gate_statuses:
        key = (gs.weir_id, gs.change_time.date())
        if key not in gate_date_map:
            gate_date_map[key] = {}
        gate_date_map[key][gs.gate_number] = gs.status

    strategy_data = {}

    for fs in fish_queryset:
        key = (fs.weir_id, fs.record_date)
        if key not in gate_date_map:
            continue

        gate_info = gate_date_map[key]
        strategy_parts = []
        for gate_num in sorted(gate_info.keys()):
            status = '开' if gate_info[gate_num] == 'open' else '关'
            strategy_parts.append(f'{gate_num}{status}')
        strategy = ', '.join(strategy_parts)

        open_count = sum(1 for s in gate_info.values() if s == 'open')
        closed_count = sum(1 for s in gate_info.values() if s == 'closed')

        wl = water_date_map.get(key)
        water_level = wl.water_level if wl else None
        flow_rate = wl.flow_rate if wl else None
        weather = wl.weather if wl else None

        if strategy not in strategy_data:
            strategy_data[strategy] = {
                'strategy': strategy,
                'open_gate_count': open_count,
                'closed_gate_count': closed_count,
                'total_gate_count': open_count + closed_count,
                'open_ratio': round(open_count / (open_count + closed_count) * 100, 1) if (open_count + closed_count) > 0 else 0,
                'fish_school_count': 0,
                'total_fish_estimated': 0,
                'total_harvest_weight': 0,
                'total_harvest_quantity': 0,
                'species_passing': {},
                'water_level_samples': [],
                'flow_rate_samples': [],
                'weather_occurrences': {},
                'aggregation_points': [],
            }

        strategy_data[strategy]['fish_school_count'] += 1
        strategy_data[strategy]['total_fish_estimated'] += fs.estimated_count

        if fs.fish_type not in strategy_data[strategy]['species_passing']:
            strategy_data[strategy]['species_passing'][fs.fish_type] = {
                'count': 0,
                'total_fish': 0,
            }
        strategy_data[strategy]['species_passing'][fs.fish_type]['count'] += 1
        strategy_data[strategy]['species_passing'][fs.fish_type]['total_fish'] += fs.estimated_count

        if water_level is not None:
            strategy_data[strategy]['water_level_samples'].append(water_level)
        if flow_rate is not None:
            strategy_data[strategy]['flow_rate_samples'].append(flow_rate)
        if weather:
            if weather not in strategy_data[strategy]['weather_occurrences']:
                strategy_data[strategy]['weather_occurrences'][weather] = 0
            strategy_data[strategy]['weather_occurrences'][weather] += 1

        strategy_data[strategy]['aggregation_points'].append({
            'date': fs.record_date,
            'species': fs.fish_type,
            'count': fs.estimated_count,
            'direction': fs.direction,
            'time': fs.observe_time,
        })

    for hr in harvest_queryset:
        key = (hr.weir_id, hr.record_date)
        if key not in gate_date_map:
            continue

        gate_info = gate_date_map[key]
        strategy_parts = []
        for gate_num in sorted(gate_info.keys()):
            status = '开' if gate_info[gate_num] == 'open' else '关'
            strategy_parts.append(f'{gate_num}{status}')
        strategy = ', '.join(strategy_parts)

        if strategy in strategy_data:
            strategy_data[strategy]['total_harvest_weight'] += hr.weight
            strategy_data[strategy]['total_harvest_quantity'] += hr.quantity

    for strategy, data in strategy_data.items():
        data['total_fish_estimated'] = round(data['total_fish_estimated'], 2)
        data['total_harvest_weight'] = round(data['total_harvest_weight'], 2)

        if data['fish_school_count'] > 0:
            data['avg_fish_per_occurrence'] = round(data['total_fish_estimated'] / data['fish_school_count'], 2)
        else:
            data['avg_fish_per_occurrence'] = 0

        if data['total_fish_estimated'] > 0:
            data['conversion_rate'] = round(data['total_harvest_weight'] / data['total_fish_estimated'] * 100, 2)
        else:
            data['conversion_rate'] = 0

        if data['water_level_samples']:
            data['avg_water_level'] = round(sum(data['water_level_samples']) / len(data['water_level_samples']), 2)
        else:
            data['avg_water_level'] = None

        if data['flow_rate_samples']:
            data['avg_flow_rate'] = round(sum(data['flow_rate_samples']) / len(data['flow_rate_samples']), 2)
        else:
            data['avg_flow_rate'] = None

        sorted_species = sorted(
            data['species_passing'].items(),
            key=lambda x: -x[1]['total_fish']
        )
        data['top_species'] = [
            {
                'species': s,
                'count': d['count'],
                'total_fish': round(d['total_fish'], 2),
                'percentage': round(d['total_fish'] / data['total_fish_estimated'] * 100, 1) if data['total_fish_estimated'] > 0 else 0,
            }
            for s, d in sorted_species[:5]
        ]

        data['aggregation_density'] = round(len(data['aggregation_points']) / max(data['fish_school_count'], 1), 2)

        top_aggregations = sorted(
            data['aggregation_points'],
            key=lambda x: -x['count']
        )[:5]
        data['top_aggregations'] = top_aggregations

        if data['weather_occurrences']:
            top_weather = sorted(
                data['weather_occurrences'].items(),
                key=lambda x: -x[1]
            )[:3]
            data['dominant_weather'] = ', '.join([f'{w}({c}次)' for w, c in top_weather])
        else:
            data['dominant_weather'] = '数据不足'

    result = sorted(strategy_data.values(), key=lambda x: -x['conversion_rate'])
    return result


def get_gate_strategy_recommendations(filters=None):
    filters = filters or {}
    synergy_data = get_gate_synergy_analysis(filters)
    path_analysis = get_species_migration_path_analysis(filters)

    recommendations = []

    species_list = [d['species'] for d in path_analysis[:8]]

    for species in species_list:
        species_data = next((d for d in path_analysis if d['species'] == species), None)
        if not species_data:
            continue

        best_season = max(
            species_data['seasonal_distribution'].items(),
            key=lambda x: x[1]
        )
        best_water = max(
            species_data['water_level_distribution'].items(),
            key=lambda x: x[1]
        )
        best_flow = max(
            species_data['flow_rate_distribution'].items(),
            key=lambda x: x[1]
        )

        best_weather = None
        if species_data['weather_distribution']:
            best_weather = max(
                species_data['weather_distribution'].items(),
                key=lambda x: x[1]
            )

        best_strategies_for_species = []
        for strategy in synergy_data:
            species_in_strategy = next(
                (s for s in strategy['top_species'] if s['species'] == species),
                None
            )
            if species_in_strategy and strategy['conversion_rate'] > 0:
                best_strategies_for_species.append({
                    'strategy': strategy['strategy'],
                    'conversion_rate': strategy['conversion_rate'],
                    'species_contribution': species_in_strategy['percentage'],
                    'avg_water_level': strategy['avg_water_level'],
                    'avg_flow_rate': strategy['avg_flow_rate'],
                    'dominant_weather': strategy['dominant_weather'],
                })

        best_strategies_for_species.sort(key=lambda x: -x['conversion_rate'])

        season_name_map = {
            'spring': '春季', 'summer': '夏季',
            'autumn': '秋季', 'winter': '冬季',
        }

        recommendation = {
            'species': species,
            'total_fish_estimated': species_data['total_fish_estimated'],
            'total_harvest_weight': species_data.get('total_harvest_weight', 0),
            'conversion_rate': species_data.get('conversion_rate', 0),
            'optimal_conditions': {
                'best_season': season_name_map.get(best_season[0], best_season[0]),
                'best_season_fish_count': best_season[1],
                'best_water_level': best_water[0],
                'best_water_fish_count': best_water[1],
                'best_flow_rate': best_flow[0],
                'best_flow_fish_count': best_flow[1],
                'best_weather': best_weather[0] if best_weather else '数据不足',
                'best_weather_fish_count': best_weather[1] if best_weather else 0,
            },
            'gate_strategies': best_strategies_for_species[:3],
            'migration_pattern': {
                'upstream_count': species_data['upstream_count'],
                'downstream_count': species_data['downstream_count'],
                'preferred_direction': '逆流而上' if species_data['upstream_count'] > species_data['downstream_count'] else '顺流而下',
            },
            'strategy_advice': generate_strategy_advice(species_data, best_strategies_for_species),
        }
        recommendations.append(recommendation)

    overall_best_strategies = []
    for strategy in synergy_data[:5]:
        overall_best_strategies.append({
            'strategy': strategy['strategy'],
            'conversion_rate': strategy['conversion_rate'],
            'total_fish': strategy['total_fish_estimated'],
            'total_harvest': strategy['total_harvest_weight'],
            'top_species': strategy['top_species'],
            'avg_water_level': strategy['avg_water_level'],
            'avg_flow_rate': strategy['avg_flow_rate'],
            'open_ratio': strategy['open_ratio'],
            'dominant_weather': strategy['dominant_weather'],
        })

    return {
        'species_recommendations': recommendations,
        'overall_best_strategies': overall_best_strategies,
    }


def generate_strategy_advice(species_data, best_strategies):
    advice_parts = []

    if species_data['upstream_count'] > species_data['downstream_count']:
        advice_parts.append(f'该鱼种偏好逆流而上，建议在鱼梁上游侧增加闸口开启数量')
    else:
        advice_parts.append(f'该鱼种偏好顺流而下，建议在鱼梁下游侧增加闸口开启数量')

    if best_strategies:
        best = best_strategies[0]
        if best['conversion_rate'] >= 50:
            advice_parts.append(f'闸口策略「{best["strategy"]}」捕获转化率达{best["conversion_rate"]}%，为最优选择')
        elif best['conversion_rate'] >= 20:
            advice_parts.append(f'推荐使用闸口策略「{best["strategy"]}」，转化率{best["conversion_rate"]}%')
        else:
            advice_parts.append(f'当前闸口策略效果一般，建议尝试不同的闸口组合')

    if species_data.get('conversion_rate', 0) < 10:
        advice_parts.append('整体捕获转化率偏低，建议优化作业时机和闸口策略组合')

    if not advice_parts:
        advice_parts.append('数据充足，建议持续观测以获得更精准的策略建议')

    return '；'.join(advice_parts)


def get_comprehensive_migration_analysis(filters=None):
    filters = filters or {}

    fish_summary = get_fish_school_summary(filters)
    harvest_summary = get_harvest_summary(filters)
    monthly_trend = get_monthly_migration_trend(filters)
    seasonal_analysis = get_seasonal_migration_analysis(filters)
    water_level_analysis = get_water_level_migration_analysis(filters)
    weather_analysis = get_weather_migration_analysis(filters)
    species_analysis = get_species_migration_analysis(filters)
    correlations = calculate_correlation_analysis(filters)
    key_factors = get_key_factor_ranking(filters)
    warnings = generate_migration_warnings(filters)

    species_path_analysis = get_species_migration_path_analysis(filters)
    species_response_comparison = get_species_response_comparison(filters)
    gate_synergy_analysis = get_gate_synergy_analysis(filters)
    gate_strategy_recommendations = get_gate_strategy_recommendations(filters)

    has_data = (fish_summary['school_record_count'] > 0 or
                harvest_summary['harvest_record_count'] > 0)

    return {
        'has_data': has_data,
        'fish_summary': fish_summary,
        'harvest_summary': harvest_summary,
        'monthly_trend': monthly_trend,
        'seasonal_analysis': seasonal_analysis,
        'water_level_analysis': water_level_analysis,
        'weather_analysis': weather_analysis,
        'species_analysis': species_analysis,
        'correlations': correlations,
        'key_factors': key_factors,
        'warnings': warnings,
        'species_path_analysis': species_path_analysis,
        'species_response_comparison': species_response_comparison,
        'gate_synergy_analysis': gate_synergy_analysis,
        'gate_strategy_recommendations': gate_strategy_recommendations,
    }
