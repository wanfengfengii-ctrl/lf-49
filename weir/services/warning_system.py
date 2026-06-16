from django.utils import timezone
from .utils import (get_season, get_season_name, round_value)
from .fish_migration import FishMigrationService


class WarningSystemService:
    @staticmethod
    def generate_migration_warnings(filters=None):
        filters = filters or {}
        warnings = []

        today = timezone.now().date()
        current_month = today.month
        current_season = get_season(current_month)

        seasonal_data = FishMigrationService.get_seasonal_migration_analysis(filters)
        monthly_trend = FishMigrationService.get_monthly_migration_trend(filters)

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

        correlations = FishMigrationService.calculate_correlation_analysis(filters)
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

        water_data = FishMigrationService.get_water_level_migration_analysis(filters)
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


def generate_migration_warnings(filters=None):
    return WarningSystemService.generate_migration_warnings(filters)
