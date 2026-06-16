from ..models import FishSchool, HarvestRecord, WaterLevel, GateStatus, HarvestEstimate
from .utils import (get_season, get_season_name, WATER_INTERVALS, FLOW_INTERVALS, round_value, safe_divide, generate_gate_config_key, parse_date)
from .filter_service import (FishMigrationFilterService, WaterLevelFilterService, GateFilterService, HarvestFilterService)
from .fish_migration import FishMigrationService


class GateAnalysisService:
    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def get_species_migration_path_analysis(filters=None):
        filters = filters or {}
        fish_queryset, harvest_queryset, water_queryset = FishMigrationService._get_filtered_datasets(filters)

        water_date_map = FishMigrationService._get_water_date_map(water_queryset)
        gate_date_map = GateFilterService.get_gate_date_map(filters)

        season_names = {
            'spring': '春季', 'summer': '夏季',
            'autumn': '秋季', 'winter': '冬季',
        }

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
                    'water_level_distribution': {label: 0 for _, _, label in WATER_INTERVALS},
                    'flow_rate_distribution': {label: 0 for _, _, label in FLOW_INTERVALS},
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
                for min_val, max_val, label in WATER_INTERVALS:
                    if min_val <= wl.water_level < max_val:
                        species_path_data[species]['water_level_distribution'][label] += fs.estimated_count
                        break
                for min_val, max_val, label in FLOW_INTERVALS:
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
                    'water_level_distribution': {label: 0 for _, _, label in WATER_INTERVALS},
                    'flow_rate_distribution': {label: 0 for _, _, label in FLOW_INTERVALS},
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

    @staticmethod
    def get_species_response_comparison(filters=None):
        filters = filters or {}
        path_analysis = GateAnalysisService.get_species_migration_path_analysis(filters)

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

    @staticmethod
    def get_gate_synergy_analysis(filters=None):
        filters = filters or {}
        fish_queryset, harvest_queryset, water_queryset = FishMigrationService._get_filtered_datasets(filters)

        water_date_map = FishMigrationService._get_water_date_map(water_queryset)
        gate_date_map = GateFilterService.get_gate_date_map(filters)

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


def get_typical_gate_configs(weir, season=None, top_n=5):
    return GateAnalysisService.get_typical_gate_configs(weir, season, top_n)


def get_historical_operation_patterns(weir, start_date=None, end_date=None):
    return GateAnalysisService.get_historical_operation_patterns(weir, start_date, end_date)


def get_species_migration_path_analysis(filters=None):
    return GateAnalysisService.get_species_migration_path_analysis(filters)


def get_species_response_comparison(filters=None):
    return GateAnalysisService.get_species_response_comparison(filters)


def get_gate_synergy_analysis(filters=None):
    return GateAnalysisService.get_gate_synergy_analysis(filters)
