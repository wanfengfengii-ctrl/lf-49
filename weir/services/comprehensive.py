from .harvest_estimation import HarvestEstimationService
from .trend_analysis import TrendAnalysisService
from .fish_migration import FishMigrationService
from .gate_analysis import GateAnalysisService
from .warning_system import WarningSystemService
from .strategy_recommendation import StrategyRecommendationService


class ComprehensiveAnalysisService:
    @staticmethod
    def get_comprehensive_harvest_analysis(filters=None):
        filters = filters or {}

        summary = TrendAnalysisService.get_comprehensive_analysis(filters)
        seasonal_data = TrendAnalysisService.get_seasonal_analysis(filters)
        water_level_data = TrendAnalysisService.get_water_level_interval_analysis(filters)
        flow_rate_data = TrendAnalysisService.get_flow_rate_analysis(filters)
        weather_data = TrendAnalysisService.get_weather_analysis(filters)
        monthly_data = HarvestEstimationService.get_monthly_comparison(filters)
        heatmap_data = TrendAnalysisService.get_strategy_heatmap_data(filters)
        multi_dim_data = TrendAnalysisService.get_multi_dimensional_comparison(filters)

        return {
            'summary': summary,
            'seasonal_data': seasonal_data,
            'water_level_data': water_level_data,
            'flow_rate_data': flow_rate_data,
            'weather_data': weather_data,
            'monthly_data': monthly_data,
            'heatmap_data': heatmap_data,
            'multi_dim_data': multi_dim_data,
        }

    @staticmethod
    def get_comprehensive_migration_analysis(filters=None):
        filters = filters or {}

        fish_summary = FishMigrationService.get_fish_school_summary(filters)
        harvest_summary = FishMigrationService.get_harvest_summary(filters)
        monthly_trend = FishMigrationService.get_monthly_migration_trend(filters)
        seasonal_analysis = FishMigrationService.get_seasonal_migration_analysis(filters)
        water_level_analysis = FishMigrationService.get_water_level_migration_analysis(filters)
        weather_analysis = FishMigrationService.get_weather_migration_analysis(filters)
        species_analysis = FishMigrationService.get_species_migration_analysis(filters)
        correlations = FishMigrationService.calculate_correlation_analysis(filters)
        key_factors = FishMigrationService.get_key_factor_ranking(filters)
        warnings = WarningSystemService.generate_migration_warnings(filters)

        species_path_analysis = GateAnalysisService.get_species_migration_path_analysis(filters)
        species_response_comparison = GateAnalysisService.get_species_response_comparison(filters)
        gate_synergy_analysis = GateAnalysisService.get_gate_synergy_analysis(filters)
        gate_strategy_recommendations = StrategyRecommendationService.get_gate_strategy_recommendations(filters)

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


def get_comprehensive_analysis(filters=None):
    return ComprehensiveAnalysisService.get_comprehensive_harvest_analysis(filters)


def get_comprehensive_migration_analysis(filters=None):
    return ComprehensiveAnalysisService.get_comprehensive_migration_analysis(filters)
