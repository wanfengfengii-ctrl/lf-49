from datetime import timedelta
from django.db.models import Q, Sum
from django.utils import timezone
from ..models import HarvestRecord, WaterLevel, HarvestEstimate, FishSchool
from .utils import (parse_date, get_season, get_season_name, get_season_factor, get_water_level_factor, get_active_gate_strategy, get_water_level_for_date, WEATHER_FACTOR_MAP, round_value)
from .exceptions import InvalidParameterError
from .harvest_estimation import HarvestEstimationService
from .trend_analysis import TrendAnalysisService


class SimulationService:
    @staticmethod
    def simulate_harvest(weir, sim_date, water_level, flow_rate, weather, gate_config, historical_period='all'):
        sim_date = parse_date(sim_date)
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
        weather_factor = WEATHER_FACTOR_MAP.get(weather, 1.0)

        if similar_with_conditions:
            avg_weight = sum(r['weight'] for r in similar_with_conditions) / len(similar_with_conditions)
            base_estimate = avg_weight
            confidence = min(95, 50 + len(similar_with_conditions) * 5)
        else:
            baseline = water_level * 2.0
            base_estimate = baseline
            confidence = 40

        estimated_weight = round_value(base_estimate * season_factor * water_factor * weather_factor)

        gate_count_open = gate_config.count('开') if gate_config else 0
        gate_efficiency_factor = 1.0 + (gate_count_open * 0.1) if gate_count_open > 0 else 0.5
        estimated_weight = round_value(estimated_weight * gate_efficiency_factor)

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

    @staticmethod
    def simulate_multiple_strategies(weir, sim_date, water_level, flow_rate, weather, strategies, historical_period='all'):
        results = []
        
        for strategy in strategies:
            sim_result = SimulationService.simulate_harvest(
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
                result['advantage'] = round_value(results[0]['estimated_weight'] - result['estimated_weight'])
        
        return results

    @staticmethod
    def reconstruct_historical_operation(weir, target_date):
        target_date = parse_date(target_date)
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
            reconstructed = SimulationService.simulate_harvest(
                weir=weir,
                sim_date=target_date,
                water_level=water_level.water_level,
                flow_rate=water_level.flow_rate,
                weather=water_level.weather,
                gate_config=gate_strategy,
                historical_period='all'
            )
            context['reconstructed_estimate'] = reconstructed
            context['reconstruction_accuracy'] = SimulationService.calculate_reconstruction_accuracy(harvest, reconstructed['estimated_weight'])
        
        return context

    @staticmethod
    def calculate_reconstruction_accuracy(actual, estimated):
        if actual <= 0 or estimated <= 0:
            return None
        return round_value((1 - abs(actual - estimated) / actual) * 100)

    @staticmethod
    def get_traditional_fishing_calendar(weir):
        season_data = TrendAnalysisService.get_seasonal_analysis({'weir': weir})
        
        calendar = []
        for season in season_data:
            calendar.append({
                'season': season['season_name'],
                'season_code': season['season'],
                'avg_efficiency': season['efficiency'],
                'avg_water_level': season['avg_water_level'],
                'avg_flow_rate': season['avg_flow_rate'],
                'recommendation': SimulationService.generate_season_recommendation(season),
            })
        
        return calendar

    @staticmethod
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


def simulate_harvest(weir, sim_date, water_level, flow_rate, weather, gate_config, historical_period='all'):
    return SimulationService.simulate_harvest(weir, sim_date, water_level, flow_rate, weather, gate_config, historical_period)


def simulate_multiple_strategies(weir, sim_date, water_level, flow_rate, weather, strategies, historical_period='all'):
    return SimulationService.simulate_multiple_strategies(weir, sim_date, water_level, flow_rate, weather, strategies, historical_period)


def reconstruct_historical_operation(weir, target_date):
    return SimulationService.reconstruct_historical_operation(weir, target_date)


def calculate_reconstruction_accuracy(actual, estimated):
    return SimulationService.calculate_reconstruction_accuracy(actual, estimated)


def get_traditional_fishing_calendar(weir):
    return SimulationService.get_traditional_fishing_calendar(weir)


def generate_season_recommendation(season_data):
    return SimulationService.generate_season_recommendation(season_data)
