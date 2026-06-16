from datetime import datetime, date
from django.db.models import Sum
from ..models import GateStatus, WaterLevel, HarvestRecord


SEASON_NAMES = {
    'spring': '春季',
    'summer': '夏季',
    'autumn': '秋季',
    'winter': '冬季',
}

SEASON_MONTHS = {
    'spring': [3, 4, 5],
    'summer': [6, 7, 8],
    'autumn': [9, 10, 11],
    'winter': [12, 1, 2],
}

WATER_INTERVALS = [
    (0, 1, '0-1米'),
    (1, 2, '1-2米'),
    (2, 3, '2-3米'),
    (3, 4, '3-4米'),
    (4, 100, '4米以上'),
]

FLOW_INTERVALS = [
    (0, 0.5, '0-0.5 m/s'),
    (0.5, 1, '0.5-1 m/s'),
    (1, 1.5, '1-1.5 m/s'),
    (1.5, 2, '1.5-2 m/s'),
    (2, 100, '2 m/s以上'),
]

WEATHER_FACTOR_MAP = {
    '晴': 1.0, '多云': 0.95, '阴': 0.9,
    '小雨': 0.85, '中雨': 0.7, '大雨': 0.5,
    '暴雨': 0.3, '雪': 0.6, '雾': 0.8,
}


def parse_date(target_date):
    if isinstance(target_date, str):
        return datetime.strptime(target_date, '%Y-%m-%d').date()
    if isinstance(target_date, datetime):
        return target_date.date()
    if isinstance(target_date, date):
        return target_date
    raise ValueError(f'Invalid date type: {type(target_date)}')


def get_season(month):
    if month in [3, 4, 5]:
        return 'spring'
    elif month in [6, 7, 8]:
        return 'summer'
    elif month in [9, 10, 11]:
        return 'autumn'
    else:
        return 'winter'


def get_season_name(season_code):
    return SEASON_NAMES.get(season_code, '未知')


def get_season_factor(target_date):
    if isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
    month = target_date.month
    if month in [3, 4, 5]:
        return 1.3
    elif month in [6, 7, 8]:
        return 1.5
    elif month in [9, 10, 11]:
        return 1.1
    else:
        return 0.8


def get_water_level_factor(water_level):
    if water_level < 1.0:
        return 0.5
    elif water_level < 2.0:
        return 0.8
    elif water_level < 3.0:
        return 1.2
    elif water_level < 4.0:
        return 1.5
    else:
        return 1.0


def get_active_gate_strategy(weir, target_date):
    target_date = parse_date(target_date)
    gate_statuses = GateStatus.objects.filter(
        weir=weir,
        change_time__date__lte=target_date
    ).order_by('gate_number', '-change_time')

    latest_status = {}
    for gs in gate_statuses:
        if gs.gate_number not in latest_status:
            latest_status[gs.gate_number] = gs.status

    if not latest_status:
        return '默认策略'

    return generate_gate_config_key(latest_status)


def generate_gate_config_key(gate_status_dict):
    parts = []
    for gate_num in sorted(gate_status_dict.keys()):
        status = '开' if gate_status_dict[gate_num] == 'open' else '关'
        parts.append(f'{gate_num}{status}')
    return ', '.join(parts)


def get_actual_weight_for_date(weir, target_date):
    target_date = parse_date(target_date)
    actual = HarvestRecord.objects.filter(
        weir=weir,
        record_date=target_date
    ).aggregate(total=Sum('weight'))['total']
    return actual or 0.0


def get_water_level_for_date(weir, target_date):
    target_date = parse_date(target_date)
    return WaterLevel.objects.filter(
        weir=weir,
        record_date=target_date,
        is_primary=True
    ).first()


def get_interval_label(value, intervals):
    for min_val, max_val, label in intervals:
        if min_val <= value < max_val:
            return label
    return intervals[-1][2]


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


def round_value(value, decimals=2):
    if value is None:
        return None
    return round(value, decimals)


def safe_divide(numerator, denominator, default=0.0):
    if denominator == 0:
        return default
    return numerator / denominator
