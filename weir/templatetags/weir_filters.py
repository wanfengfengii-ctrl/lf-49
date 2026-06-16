from django import template

register = template.Library()


@register.filter
def pluck(list_of_dicts, key):
    return [item.get(key) for item in list_of_dicts]
