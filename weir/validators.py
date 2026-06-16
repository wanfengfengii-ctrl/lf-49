from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_non_negative(value):
    if value < 0:
        raise ValidationError(
            _('%(value)s 不能为负数'),
            params={'value': value},
        )


def validate_positive(value):
    if value <= 0:
        raise ValidationError(
            _('%(value)s 必须大于0'),
            params={'value': value},
        )


def validate_year(value):
    if value < 1000 or value > 2100:
        raise ValidationError(
            _('%(value)s 年份格式不正确'),
            params={'value': value},
        )
