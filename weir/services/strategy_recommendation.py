from .utils import (get_season_name, round_value)
from .trend_analysis import TrendAnalysisService
from .fish_migration import FishMigrationService
from .gate_analysis import (
    get_gate_synergy_analysis,
    get_species_migration_path_analysis
)


class StrategyRecommendationService:
    @staticmethod
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
                'strategy_advice': StrategyRecommendationService.generate_strategy_advice(species_data, best_strategies_for_species),
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

    @staticmethod
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

    @staticmethod
    def get_comprehensive_strategy_analysis(filters=None):
        filters = filters or {}

        strategy_data = TrendAnalysisService.get_strategy_efficiency_comparison(filters)

        analysis_result = []
        for strategy in strategy_data:
            strategy_filters = filters.copy()
            strategy_filters['gate_strategy'] = strategy['strategy']

            seasonal_breakdown = TrendAnalysisService.get_seasonal_analysis(strategy_filters)
            water_breakdown = TrendAnalysisService.get_water_level_interval_analysis(strategy_filters)

            optimal_conditions = StrategyRecommendationService.find_optimal_conditions(strategy_filters)

            analysis_result.append({
                'strategy': strategy,
                'seasonal_breakdown': seasonal_breakdown,
                'water_breakdown': water_breakdown,
                'optimal_conditions': optimal_conditions,
            })

        return analysis_result

    @staticmethod
    def find_optimal_conditions(filters=None):
        filters = filters or {}

        seasonal_data = TrendAnalysisService.get_seasonal_analysis(filters)
        water_data = TrendAnalysisService.get_water_level_interval_analysis(filters)
        flow_data = TrendAnalysisService.get_flow_rate_analysis(filters)
        weather_data = TrendAnalysisService.get_weather_analysis(filters)

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


def get_gate_strategy_recommendations(filters=None):
    return StrategyRecommendationService.get_gate_strategy_recommendations(filters)


def generate_strategy_advice(species_data, best_strategies):
    return StrategyRecommendationService.generate_strategy_advice(species_data, best_strategies)


def get_comprehensive_strategy_analysis(filters=None):
    return StrategyRecommendationService.get_comprehensive_strategy_analysis(filters)


def find_optimal_conditions(filters=None):
    return StrategyRecommendationService.find_optimal_conditions(filters)
