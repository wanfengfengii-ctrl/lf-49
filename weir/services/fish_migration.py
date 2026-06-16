from django.db.models import Sum, Count
from ..models import FishSchool, HarvestRecord, WaterLevel, GateStatus
from .utils import (
    get_season, get_season_name, WATER_INTERVALS, FLOW_INTERVALS,
    pearson_correlation, interpret_correlation, round_value, safe_divide,
    generate_gate_config_key
)
from .filter_service import (
    FishMigrationFilterService, WaterLevelFilterService, GateFilterService
)


class FishMigrationService:
    @staticmethod
    def get_available_fish_species():
        from_schools = list(
            FishSchool.objects.values_list('fish_type', flat=True).distinct()
        )
        from_harvests = list(
            HarvestRecord.objects.values_list('fish_species', flat=True).distinct()
        )
        all_species = list(set(from_schools + from_harvests))
        return sorted([s for s in all_species if s])

    @staticmethod
    def _get_filtered_datasets(filters=None):
        filters = filters or {}
        fish_queryset = FishSchool.objects.all()
        fish_queryset = FishMigrationFilterService.apply_fish_migration_filters(fish_queryset, filters)

        harvest_queryset = HarvestRecord.objects.all()
        harvest_queryset = FishMigrationFilterService.apply_harvest_filters(harvest_queryset, filters)

        water_queryset = WaterLevelFilterService.get_filtered_queryset(filters)

        return fish_queryset, harvest_queryset, water_queryset

    @staticmethod
    def _get_water_date_map(water_queryset):
        water_date_map = {}
        for wl in water_queryset:
            key = (wl.weir_id, wl.record_date)
            water_date_map[key] = wl
        return water_date_map

    @staticmethod
    def _get_gate_date_map(filters):
        return GateFilterService.get_gate_date_map(filters)

    @staticmethod
    def get_fish_school_summary(filters=None):
        filters = filters or {}
        queryset = FishSchool.objects.all()
        queryset = FishMigrationFilterService.apply_fish_migration_filters(queryset, filters)

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
            d['total_estimated'] = round_value(d['total_estimated'])

        return {
            'total_fish_count': total_count,
            'school_record_count': record_count,
            'weir_count': weir_count,
            'species_count': species_count,
            'direction_stats': list(direction_stats.values()),
        }

    @staticmethod
    def get_harvest_summary(filters=None):
        filters = filters or {}
        queryset = HarvestRecord.objects.all()
        queryset = FishMigrationFilterService.apply_harvest_filters(queryset, filters)

        total_weight = queryset.aggregate(total=Sum('weight'))['total'] or 0
        total_quantity = queryset.aggregate(total=Sum('quantity'))['total'] or 0
        record_count = queryset.count()
        species_count = queryset.values('fish_species').distinct().count()

        return {
            'total_weight': round_value(total_weight),
            'total_quantity': total_quantity,
            'harvest_record_count': record_count,
            'species_count': species_count,
        }

    @staticmethod
    def get_monthly_migration_trend(filters=None):
        filters = filters or {}
        fish_queryset, harvest_queryset, _ = FishMigrationService._get_filtered_datasets(filters)

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
            d['total_fish_estimated'] = round_value(d['total_fish_estimated'])
            d['harvest_weight'] = round_value(d['harvest_weight'])
            d['conversion_rate'] = round_value(safe_divide(d['harvest_weight'], d['total_fish_estimated']) * 100)
            result.append(d)

        return result

    @staticmethod
    def _get_dimension_analysis(filters, dimension_func):
        filters = filters or {}
        fish_queryset, harvest_queryset, water_queryset = FishMigrationService._get_filtered_datasets(filters)
        return dimension_func(fish_queryset, harvest_queryset, water_queryset)

    @staticmethod
    def get_seasonal_migration_analysis(filters=None):
        def analyze(fish_queryset, harvest_queryset, water_queryset):
            water_date_map = FishMigrationService._get_water_date_map(water_queryset)

            seasonal_data = {}
            for season in ['spring', 'summer', 'autumn', 'winter']:
                seasonal_data[season] = {
                    'season': season,
                    'season_name': get_season_name(season),
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
                    data['avg_water_level'] = round_value(data['avg_water_level'] / data['water_record_count'])
                    data['avg_flow_rate'] = round_value(data['avg_flow_rate'] / data['water_record_count'])
                data['total_fish_estimated'] = round_value(data['total_fish_estimated'])
                data['harvest_weight'] = round_value(data['harvest_weight'])
                data['conversion_rate'] = round_value(safe_divide(data['harvest_weight'], data['total_fish_estimated']) * 100)
                if data['fish_school_count'] > 0:
                    data['avg_school_size'] = round_value(data['total_fish_estimated'] / data['fish_school_count'])
                else:
                    data['avg_school_size'] = 0

            season_order = ['spring', 'summer', 'autumn', 'winter']
            return [seasonal_data[s] for s in season_order]

        return FishMigrationService._get_dimension_analysis(filters, analyze)

    @staticmethod
    def get_water_level_migration_analysis(filters=None):
        def analyze(fish_queryset, harvest_queryset, water_queryset):
            water_date_map = FishMigrationService._get_water_date_map(water_queryset)

            interval_data = {}
            for min_val, max_val, label in WATER_INTERVALS:
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
                    for min_val, max_val, label in WATER_INTERVALS:
                        if min_val <= wl.water_level < max_val:
                            interval_data[label]['fish_school_count'] += 1
                            interval_data[label]['total_fish_estimated'] += fs.estimated_count
                            break

            for hr in harvest_queryset:
                key = (hr.weir_id, hr.record_date)
                if key in water_date_map:
                    wl = water_date_map[key]
                    for min_val, max_val, label in WATER_INTERVALS:
                        if min_val <= wl.water_level < max_val:
                            interval_data[label]['harvest_weight'] += hr.weight
                            interval_data[label]['harvest_quantity'] += hr.quantity
                            interval_data[label]['harvest_count'] += 1
                            break

            for label, data in interval_data.items():
                data['total_fish_estimated'] = round_value(data['total_fish_estimated'])
                data['harvest_weight'] = round_value(data['harvest_weight'])
                data['conversion_rate'] = round_value(safe_divide(data['harvest_weight'], data['total_fish_estimated']) * 100)
                if data['fish_school_count'] > 0:
                    data['avg_school_size'] = round_value(data['total_fish_estimated'] / data['fish_school_count'])
                else:
                    data['avg_school_size'] = 0

            return [interval_data[label] for _, _, label in WATER_INTERVALS]

        return FishMigrationService._get_dimension_analysis(filters, analyze)

    @staticmethod
    def get_weather_migration_analysis(filters=None):
        def analyze(fish_queryset, harvest_queryset, water_queryset):
            water_date_map = FishMigrationService._get_water_date_map(water_queryset)

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
                data['total_fish_estimated'] = round_value(data['total_fish_estimated'])
                data['harvest_weight'] = round_value(data['harvest_weight'])
                data['conversion_rate'] = round_value(safe_divide(data['harvest_weight'], data['total_fish_estimated']) * 100)
                if data['fish_school_count'] > 0:
                    data['avg_school_size'] = round_value(data['total_fish_estimated'] / data['fish_school_count'])
                else:
                    data['avg_school_size'] = 0

            return sorted(weather_data.values(), key=lambda x: -x['harvest_weight'])

        return FishMigrationService._get_dimension_analysis(filters, analyze)

    @staticmethod
    def get_species_migration_analysis(filters=None):
        def analyze(fish_queryset, harvest_queryset, water_queryset):
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
                data['total_fish_estimated'] = round_value(data['total_fish_estimated'])
                data['harvest_weight'] = round_value(data['harvest_weight'])
                data['conversion_rate'] = round_value(safe_divide(data['harvest_weight'], data['total_fish_estimated']) * 100)
                if data['fish_school_count'] > 0:
                    data['avg_school_size'] = round_value(data['total_fish_estimated'] / data['fish_school_count'])
                else:
                    data['avg_school_size'] = 0

            return sorted(species_data.values(), key=lambda x: -x['harvest_weight'])

        return FishMigrationService._get_dimension_analysis(filters, analyze)

    @staticmethod
    def calculate_correlation_analysis(filters=None):
        filters = filters or {}
        fish_queryset, harvest_queryset, water_queryset = FishMigrationService._get_filtered_datasets(filters)
        water_date_map = FishMigrationService._get_water_date_map(water_queryset)

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

        fish_counts = [d['fish_estimated'] for d in valid_days]
        harvest_weights = [d['harvest_weight'] for d in valid_days]

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

    @staticmethod
    def get_key_factor_ranking(filters=None):
        filters = filters or {}
        correlations = FishMigrationService.calculate_correlation_analysis(filters)
        seasonal_data = FishMigrationService.get_seasonal_migration_analysis(filters)
        water_data = FishMigrationService.get_water_level_migration_analysis(filters)
        weather_data = FishMigrationService.get_weather_migration_analysis(filters)

        factors = []

        if correlations['fish_harvest_correlation'] is not None:
            factors.append({
                'factor': '鱼群数量-收获量关联',
                'category': '生态关联',
                'score': round_value(abs(correlations['fish_harvest_correlation']) * 100),
                'correlation': correlations['fish_harvest_correlation'],
                'description': '鱼群经过数量与实际收获量的相关性强度',
                'interpretation': interpret_correlation(correlations['fish_harvest_correlation']),
            })

        if correlations['water_level_fish_correlation'] is not None:
            factors.append({
                'factor': '水位-鱼群数量关联',
                'category': '水文因子',
                'score': round_value(abs(correlations['water_level_fish_correlation']) * 100),
                'correlation': correlations['water_level_fish_correlation'],
                'description': '水位高度对鱼群经过数量的影响程度',
                'interpretation': interpret_correlation(correlations['water_level_fish_correlation']),
            })

        if correlations['flow_rate_fish_correlation'] is not None:
            factors.append({
                'factor': '流速-鱼群数量关联',
                'category': '水文因子',
                'score': round_value(abs(correlations['flow_rate_fish_correlation']) * 100),
                'correlation': correlations['flow_rate_fish_correlation'],
                'description': '水流速度对鱼群经过数量的影响程度',
                'interpretation': interpret_correlation(correlations['flow_rate_fish_correlation']),
            })

        if correlations['water_level_harvest_correlation'] is not None:
            factors.append({
                'factor': '水位-收获量关联',
                'category': '水文因子',
                'score': round_value(abs(correlations['water_level_harvest_correlation']) * 100),
                'correlation': correlations['water_level_harvest_correlation'],
                'description': '水位高度对实际收获量的影响程度',
                'interpretation': interpret_correlation(correlations['water_level_harvest_correlation']),
            })

        if correlations['flow_rate_harvest_correlation'] is not None:
            factors.append({
                'factor': '流速-收获量关联',
                'category': '水文因子',
                'score': round_value(abs(correlations['flow_rate_harvest_correlation']) * 100),
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
                    'score': round_value(best_season['conversion_rate']),
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
                    'score': round_value(best_water['conversion_rate']),
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
                    'score': round_value(best_weather['conversion_rate']),
                    'correlation': None,
                    'description': f'{best_weather["weather"]}天气下鱼群捕获转化率最高',
                    'interpretation': f'转化率 {best_weather["conversion_rate"]}%，鱼群记录 {best_weather["fish_school_count"]} 次',
                })

        return sorted(factors, key=lambda x: -x['score'])


def get_available_fish_species():
    return FishMigrationService.get_available_fish_species()


def get_fish_school_summary(filters=None):
    return FishMigrationService.get_fish_school_summary(filters)


def get_harvest_summary(filters=None):
    return FishMigrationService.get_harvest_summary(filters)


def get_monthly_migration_trend(filters=None):
    return FishMigrationService.get_monthly_migration_trend(filters)


def get_seasonal_migration_analysis(filters=None):
    return FishMigrationService.get_seasonal_migration_analysis(filters)


def get_water_level_migration_analysis(filters=None):
    return FishMigrationService.get_water_level_migration_analysis(filters)


def get_weather_migration_analysis(filters=None):
    return FishMigrationService.get_weather_migration_analysis(filters)


def get_species_migration_analysis(filters=None):
    return FishMigrationService.get_species_migration_analysis(filters)


def calculate_correlation_analysis(filters=None):
    return FishMigrationService.calculate_correlation_analysis(filters)


def get_key_factor_ranking(filters=None):
    return FishMigrationService.get_key_factor_ranking(filters)
