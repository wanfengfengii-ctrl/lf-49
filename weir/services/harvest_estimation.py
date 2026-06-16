from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from ..models import Weir, WaterLevel, HarvestRecord, HarvestEstimate
from .utils import (
    parse_date, get_season_factor, get_water_level_factor,
    get_active_gate_strategy, get_actual_weight_for_date,
    get_water_level_for_date, round_value
)
from .exceptions import InvalidParameterError, DataNotFoundError
from .filter_service import HarvestFilterService


class HarvestEstimationService:
    @staticmethod
    def estimate_single_day(weir, estimate_date):
        estimate_date = parse_date(estimate_date)
        water_level_record = get_water_level_for_date(weir, estimate_date)

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
            wl = get_water_level_for_date(weir, record.record_date)
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

    @staticmethod
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

    @staticmethod
    def recalculate_estimates(weir, start_date, end_date=None):
        start_date = parse_date(start_date)
        if end_date is None:
            end_date = timezone.now().date()
        else:
            end_date = parse_date(end_date)

        if start_date > end_date:
            raise InvalidParameterError('start_date cannot be later than end_date')

        current_date = start_date
        estimates = []

        while current_date <= end_date:
            estimate_data = HarvestEstimationService.estimate_single_day(weir, current_date)
            estimate = HarvestEstimationService.save_estimate(estimate_data)
            estimates.append(estimate)
            current_date += timedelta(days=1)

        return estimates

    @staticmethod
    def recalculate_all_estimates():
        estimates = []
        for weir in Weir.objects.all():
            earliest_record = WaterLevel.objects.filter(
                weir=weir
            ).order_by('record_date').first()
            if earliest_record:
                estimates.extend(
                    HarvestEstimationService.recalculate_estimates(weir, earliest_record.record_date)
                )
        return estimates

    @staticmethod
    def get_filtered_estimates(filters=None):
        filters = filters or {}
        queryset = HarvestEstimate.objects.filter(has_water_data=True)
        return HarvestFilterService.apply_harvest_estimation_filters(queryset, filters)

    @staticmethod
    def get_monthly_trend(filters=None):
        queryset = HarvestEstimationService.get_filtered_estimates(filters)

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

        for data in monthly_data.values():
            data['estimated'] = round(data['estimated'], 2)
            data['actual'] = round(data['actual'], 2)

        return sorted(monthly_data.values(), key=lambda x: x['month'])

    @staticmethod
    def get_gate_strategy_comparison(filters=None):
        queryset = HarvestEstimationService.get_filtered_estimates(filters)

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

    @staticmethod
    def get_monthly_comparison(filters=None):
        queryset = HarvestEstimationService.get_filtered_estimates(filters)

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


def estimate_single_day(weir, estimate_date):
    return HarvestEstimationService.estimate_single_day(weir, estimate_date)


def save_estimate(estimate_data):
    return HarvestEstimationService.save_estimate(estimate_data)


def recalculate_estimates(weir, start_date, end_date=None):
    return HarvestEstimationService.recalculate_estimates(weir, start_date, end_date)


def recalculate_all_estimates():
    return HarvestEstimationService.recalculate_all_estimates()


def get_monthly_trend(weir=None, start_date=None, end_date=None):
    filters = {}
    if weir:
        filters['weir'] = weir
    if start_date:
        filters['start_date'] = start_date
    if end_date:
        filters['end_date'] = end_date
    return HarvestEstimationService.get_monthly_trend(filters)


def get_gate_strategy_comparison(weir=None, start_date=None, end_date=None):
    filters = {}
    if weir:
        filters['weir'] = weir
    if start_date:
        filters['start_date'] = start_date
    if end_date:
        filters['end_date'] = end_date
    return HarvestEstimationService.get_gate_strategy_comparison(filters)


def get_monthly_comparison(filters=None):
    return HarvestEstimationService.get_monthly_comparison(filters)
