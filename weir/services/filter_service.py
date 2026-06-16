from django.db.models import Q
from ..models import WaterLevel, GateStatus
from .utils import SEASON_MONTHS, generate_gate_config_key


class BaseFilterService:
    @staticmethod
    def apply_date_filters(queryset, filters, date_field='record_date'):
        if filters.get('start_date'):
            queryset = queryset.filter(**{f'{date_field}__gte': filters['start_date']})
        if filters.get('end_date'):
            queryset = queryset.filter(**{f'{date_field}__lte': filters['end_date']})
        return queryset

    @staticmethod
    def apply_weir_filter(queryset, filters):
        if filters.get('weir'):
            queryset = queryset.filter(weir=filters['weir'])
        return queryset

    @staticmethod
    def apply_season_filters(queryset, filters, date_field='record_date'):
        if filters.get('season'):
            season_months = []
            for s in filters['season']:
                season_months.extend(SEASON_MONTHS.get(s, []))
            if season_months:
                queryset = queryset.filter(**{f'{date_field}__month__in': season_months})
        return queryset

    @staticmethod
    def apply_month_filters(queryset, filters, date_field='record_date'):
        if filters.get('months'):
            queryset = queryset.filter(**{f'{date_field}__month__in': [int(m) for m in filters['months']]})
        return queryset

    @staticmethod
    def apply_numeric_range_filters(queryset, filters, field_name, min_param=None, max_param=None):
        min_param = min_param or f'{field_name}_min'
        max_param = max_param or f'{field_name}_max'
        if filters.get(min_param) is not None:
            queryset = queryset.filter(**{f'{field_name}__gte': filters[min_param]})
        if filters.get(max_param) is not None:
            queryset = queryset.filter(**{f'{field_name}__lte': filters[max_param]})
        return queryset


class WaterLevelFilterService(BaseFilterService):
    @staticmethod
    def apply_filters(water_queryset, filters):
        water_queryset = WaterLevelFilterService.apply_weir_filter(water_queryset, filters)
        water_queryset = WaterLevelFilterService.apply_date_filters(water_queryset, filters, 'record_date')
        water_queryset = WaterLevelFilterService.apply_season_filters(water_queryset, filters, 'record_date')
        water_queryset = WaterLevelFilterService.apply_month_filters(water_queryset, filters, 'record_date')
        water_queryset = WaterLevelFilterService.apply_numeric_range_filters(water_queryset, filters, 'water_level')
        water_queryset = WaterLevelFilterService.apply_numeric_range_filters(water_queryset, filters, 'flow_rate')
        if filters.get('weather'):
            water_queryset = water_queryset.filter(weather__in=filters['weather'])
        return water_queryset

    @staticmethod
    def get_filtered_queryset(filters=None):
        filters = filters or {}
        queryset = WaterLevel.objects.filter(is_primary=True)
        return WaterLevelFilterService.apply_filters(queryset, filters)


class GateFilterService(BaseFilterService):
    @staticmethod
    def get_gate_date_map(filters):
        gate_statuses = GateStatus.objects.all()
        if filters.get('weir'):
            gate_statuses = gate_statuses.filter(weir=filters['weir'])

        gate_date_map = {}
        for gs in gate_statuses:
            key = (gs.weir_id, gs.change_time.date())
            if key not in gate_date_map:
                gate_date_map[key] = {}
            gate_date_map[key][gs.gate_number] = gs.status
        return gate_date_map

    @staticmethod
    def get_valid_date_keys(gate_date_map, filters):
        has_gate_filter = filters.get('gate_status') or filters.get('gate_strategy')
        if not has_gate_filter:
            return None

        valid_keys = set()
        for (weir_id, record_date), gate_info in gate_date_map.items():
            strategy = generate_gate_config_key(gate_info)

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
        return valid_keys

    @staticmethod
    def apply_gate_filters(queryset, filters, date_field='record_date'):
        has_gate_filter = filters.get('gate_status') or filters.get('gate_strategy')
        if not has_gate_filter:
            return queryset

        gate_date_map = GateFilterService.get_gate_date_map(filters)
        valid_keys = GateFilterService.get_valid_date_keys(gate_date_map, filters)

        if valid_keys:
            q_objects = Q()
            for weir_id, record_date in valid_keys:
                date_filter = {f'{date_field}__gte': record_date, f'{date_field}__lte': record_date}
                q_objects |= Q(weir_id=weir_id, **date_filter)
            queryset = queryset.filter(q_objects)
        else:
            queryset = queryset.none()

        return queryset


class HarvestFilterService(BaseFilterService):
    @staticmethod
    def apply_common_filters(queryset, filters, date_field='record_date'):
        queryset = HarvestFilterService.apply_weir_filter(queryset, filters)
        queryset = HarvestFilterService.apply_date_filters(queryset, filters, date_field)
        queryset = HarvestFilterService.apply_season_filters(queryset, filters, date_field)
        queryset = HarvestFilterService.apply_month_filters(queryset, filters, date_field)
        if filters.get('gate_strategy') or filters.get('gate_status'):
            queryset = GateFilterService.apply_gate_filters(queryset, filters, date_field)
        return queryset

    @staticmethod
    def apply_harvest_estimation_filters(queryset, filters):
        queryset = queryset.filter(has_water_data=True)
        queryset = HarvestFilterService.apply_common_filters(queryset, filters, 'estimate_date')
        queryset = HarvestFilterService.apply_numeric_range_filters(queryset, filters, 'water_level')
        if filters.get('gate_strategy'):
            queryset = queryset.filter(gate_strategy__icontains=filters['gate_strategy'])
        if filters.get('gate_status'):
            status_text = '开' if filters['gate_status'] == 'open' else '关'
            queryset = queryset.filter(gate_strategy__icontains=status_text)
        return queryset

    @staticmethod
    def apply_harvest_record_filters(queryset, filters):
        queryset = HarvestFilterService.apply_common_filters(queryset, filters, 'record_date')
        if filters.get('fish_species'):
            queryset = queryset.filter(fish_species__in=filters['fish_species'])
        return queryset

    @staticmethod
    def apply_water_dependent_filters(queryset, filters, date_field='record_date'):
        has_water_filter = (
            filters.get('water_level_min') is not None or
            filters.get('water_level_max') is not None or
            filters.get('flow_rate_min') is not None or
            filters.get('flow_rate_max') is not None or
            filters.get('weather')
        )
        if has_water_filter:
            water_queryset = WaterLevelFilterService.get_filtered_queryset(filters)
            valid_dates = list(water_queryset.values_list('weir_id', 'record_date'))
            if valid_dates:
                q_objects = Q()
                for weir_id, record_date in valid_dates:
                    q_objects |= Q(weir_id=weir_id, **{date_field: record_date})
                queryset = queryset.filter(q_objects)
            else:
                queryset = queryset.none()
        return queryset


class FishMigrationFilterService(BaseFilterService):
    @staticmethod
    def apply_fish_migration_filters(fish_queryset, filters):
        fish_queryset = HarvestFilterService.apply_common_filters(fish_queryset, filters, 'record_date')
        if filters.get('fish_species'):
            fish_queryset = fish_queryset.filter(fish_type__in=filters['fish_species'])
        fish_queryset = HarvestFilterService.apply_water_dependent_filters(fish_queryset, filters, 'record_date')
        return fish_queryset

    @staticmethod
    def apply_harvest_filters(harvest_queryset, filters):
        harvest_queryset = HarvestFilterService.apply_harvest_record_filters(harvest_queryset, filters)
        harvest_queryset = HarvestFilterService.apply_water_dependent_filters(harvest_queryset, filters, 'record_date')
        return harvest_queryset
