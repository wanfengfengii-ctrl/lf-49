from django.db.models import Avg, Sum
from ..models import WaterLevel
from .utils import (
    get_season, get_season_name, WATER_INTERVALS, FLOW_INTERVALS,
    round_value, safe_divide
)
from .filter_service import (
    HarvestFilterService, WaterLevelFilterService
)
from .harvest_estimation import HarvestEstimationService


class TrendAnalysisService:
    @staticmethod
    def _get_estimates_with_water(filters=None):
        filters = filters or {}
        queryset = HarvestEstimationService.get_filtered_estimates(filters)
        water_queryset = WaterLevelFilterService.get_filtered_queryset(filters)

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

        return estimates_with_water

    @staticmethod
    def get_comprehensive_analysis(filters=None):
        filters = filters or {}
        queryset = HarvestEstimationService.get_filtered_estimates(filters)
        estimates_with_water = TrendAnalysisService._get_estimates_with_water(filters)

        total_estimated = queryset.aggregate(total=Sum('estimated_weight'))['total'] or 0
        total_actual = queryset.aggregate(total=Sum('actual_weight'))['total'] or 0
        record_count = queryset.count()
        avg_accuracy = queryset.filter(accuracy__isnull=False).aggregate(avg=Avg('accuracy'))['avg']

        return {
            'total_estimated': round_value(total_estimated),
            'total_actual': round_value(total_actual),
            'record_count': record_count,
            'avg_accuracy': round_value(avg_accuracy),
            'estimates_with_water': estimates_with_water,
        }

    @staticmethod
    def _get_interval_analysis(filters, intervals, field_name, label_getter):
        filters = filters or {}
        queryset = HarvestEstimationService.get_filtered_estimates(filters)
        water_queryset = WaterLevelFilterService.get_filtered_queryset(filters)

        water_date_map = {}
        for wl in water_queryset:
            key = (wl.weir_id, wl.record_date)
            water_date_map[key] = wl

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
            value = getattr(wl, field_name)
            for min_val, max_val, label in intervals:
                if min_val <= value < max_val:
                    interval_data[label]['total_estimated'] += est.estimated_weight
                    interval_data[label]['total_actual'] += est.actual_weight
                    interval_data[label]['count'] += 1
                    break

        for label, data in interval_data.items():
            if data['count'] > 0:
                data['total_estimated'] = round_value(data['total_estimated'])
                data['total_actual'] = round_value(data['total_actual'])
                data['efficiency'] = round_value(safe_divide(data['total_actual'], data['count']))

        return [interval_data[label] for _, _, label in intervals if interval_data[label]['count'] > 0]

    @staticmethod
    def get_seasonal_analysis(filters=None):
        filters = filters or {}
        queryset = HarvestEstimationService.get_filtered_estimates(filters)
        water_queryset = WaterLevelFilterService.get_filtered_queryset(filters)

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
                data['avg_water_level'] = round_value(data['avg_water_level'] / data['count'])
                data['avg_flow_rate'] = round_value(data['avg_flow_rate'] / data['count'])
                data['total_estimated'] = round_value(data['total_estimated'])
                data['total_actual'] = round_value(data['total_actual'])
                data['efficiency'] = round_value(safe_divide(data['total_actual'], data['count']))

        season_order = ['spring', 'summer', 'autumn', 'winter']
        return [seasonal_data[s] for s in season_order if s in seasonal_data]

    @staticmethod
    def get_water_level_interval_analysis(filters=None):
        return TrendAnalysisService._get_interval_analysis(
            filters, WATER_INTERVALS, 'water_level', lambda x: x['interval']
        )

    @staticmethod
    def get_flow_rate_analysis(filters=None):
        return TrendAnalysisService._get_interval_analysis(
            filters, FLOW_INTERVALS, 'flow_rate', lambda x: x['interval']
        )

    @staticmethod
    def get_weather_analysis(filters=None):
        filters = filters or {}
        queryset = HarvestEstimationService.get_filtered_estimates(filters)
        water_queryset = WaterLevelFilterService.get_filtered_queryset(filters)

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
                data['total_estimated'] = round_value(data['total_estimated'])
                data['total_actual'] = round_value(data['total_actual'])
                data['efficiency'] = round_value(safe_divide(data['total_actual'], data['count']))

        return sorted(weather_data.values(), key=lambda x: -x['efficiency'])

    @staticmethod
    def get_strategy_efficiency_comparison(filters=None):
        filters = filters or {}
        queryset = HarvestEstimationService.get_filtered_estimates(filters)
        water_queryset = WaterLevelFilterService.get_filtered_queryset(filters)

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
                data['total_estimated'] = round_value(data['total_estimated'])
                data['total_actual'] = round_value(data['total_actual'])
                data['avg_accuracy'] = round_value(data['avg_accuracy'] / data['count'])
                data['avg_water_level'] = round_value(data['avg_water_level'] / data['count'])
                data['avg_flow_rate'] = round_value(data['avg_flow_rate'] / data['count'])
                data['efficiency'] = round_value(safe_divide(data['total_actual'], data['count']))

        return sorted(strategy_data.values(), key=lambda x: -x['efficiency'])

    @staticmethod
    def get_strategy_heatmap_data(filters=None):
        filters = filters or {}
        queryset = HarvestEstimationService.get_filtered_estimates(filters)
        water_queryset = WaterLevelFilterService.get_filtered_queryset(filters)

        water_date_map = {}
        for wl in water_queryset:
            key = (wl.weir_id, wl.record_date)
            water_date_map[key] = wl

        season_names = {
            'spring': '春季', 'summer': '夏季',
            'autumn': '秋季', 'winter': '冬季',
        }

        heatmap_data = []
        for season in ['spring', 'summer', 'autumn', 'winter']:
            for _, _, water_label in WATER_INTERVALS:
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
            for min_val, max_val, label in WATER_INTERVALS:
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
                cell['efficiency'] = round_value(cell['efficiency'] / cell['count'])

        return heatmap_data

    @staticmethod
    def get_multi_dimensional_comparison(filters=None):
        filters = filters or {}

        seasonal_data = TrendAnalysisService.get_seasonal_analysis(filters)
        water_level_data = TrendAnalysisService.get_water_level_interval_analysis(filters)
        flow_rate_data = TrendAnalysisService.get_flow_rate_analysis(filters)
        weather_data = TrendAnalysisService.get_weather_analysis(filters)
        strategy_data = TrendAnalysisService.get_strategy_efficiency_comparison(filters)

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


def get_comprehensive_analysis(filters=None):
    return TrendAnalysisService.get_comprehensive_analysis(filters)


def get_seasonal_analysis(filters=None):
    return TrendAnalysisService.get_seasonal_analysis(filters)


def get_water_level_interval_analysis(filters=None):
    return TrendAnalysisService.get_water_level_interval_analysis(filters)


def get_flow_rate_analysis(filters=None):
    return TrendAnalysisService.get_flow_rate_analysis(filters)


def get_weather_analysis(filters=None):
    return TrendAnalysisService.get_weather_analysis(filters)


def get_strategy_efficiency_comparison(filters=None):
    return TrendAnalysisService.get_strategy_efficiency_comparison(filters)


def get_strategy_heatmap_data(filters=None):
    return TrendAnalysisService.get_strategy_heatmap_data(filters)


def get_multi_dimensional_comparison(filters=None):
    return TrendAnalysisService.get_multi_dimensional_comparison(filters)
