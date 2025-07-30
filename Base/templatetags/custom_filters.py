from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, 0)

def filter_by_status(items, status):
    return [item for item in items if item.status == status]    

def unique_items(queryset, attribute):
    seen = set()
    unique_list = []
    for item in queryset:
        value = getattr(item, attribute)
        if value not in seen:
            seen.add(value)
            unique_list.append(item)
    return unique_list


@register.filter
def filter_by_status(queryset, status):
    return queryset.filter(status=status)