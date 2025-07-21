from django.contrib import admin
from .models import InventoryItem, MachineFailure, Notification, User, AssetType, Technician, WorkOrder, MaintenanceTask, Machine, TaskInventoryUsage
from mptt.admin import MPTTModelAdmin , DraggableMPTTAdmin
from django.utils.html import format_html


admin.site.register(InventoryItem)
admin.site.register(User)
admin.site.register(Notification)
admin.site.register(MachineFailure)



# 1. إدارة AssetType (شجرة الأنواع) مع واجهة السحب والإفلات
@admin.register(AssetType)
class AssetTypeAdmin(DraggableMPTTAdmin):
    list_display = ('tree_actions', 'indented_title', 'is_template', 'get_machines_count')
    list_display_links = ('indented_title',)
    search_fields = ('name', 'description')
    list_filter = ('is_template',)
    
    def get_machines_count(self, obj):
        return obj.machine_set.count()
    get_machines_count.short_description = 'machine quantity'
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'parent', 'is_template')
        }),
    )

# 2. إدارة Machine مع فلتر حسب النوع
class MachineAdmin(admin.ModelAdmin):
    list_display = ('name', 'asset_class', 'serial_number', 'status', 'purchase_date', 'location')
    list_filter = ('asset_class', 'status', 'is_template')
    search_fields = ('name', 'serial_number', 'asset_class__name')
    raw_id_fields = ('parent_machine',)
    date_hierarchy = 'purchase_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('asset_class', 'name', 'serial_number', 'is_template')
        }),
        ('Status & Location', {
            'fields': ('status', 'purchase_date', 'location')
        }),
        ('Hierarchy', {
            'fields': ('parent_machine',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.GET.get('is_template') == '1':
            return qs.filter(is_template=True)
        return qs

admin.site.register(Machine, MachineAdmin)

# 3. إضافة إجراء لإنشاء آلة من نوع
def create_machine_from_type(modeladmin, request, queryset):
    for asset_type in queryset:
        try:
            machine = asset_type.create_machine_from_type(
                name=asset_type.name,
                serial_number=f"TEMP-{asset_type.assetid}",
                status='Operational'
            )
            request.user.message_set.create(
                message=f'{machine.name} added successfully!'
            )
        except Exception as e:
            request.user.message_set.create(
                message=f'error in adding {asset_type.name}: {str(e)}',
                level='ERROR'
            )
create_machine_from_type.short_description = "إنشاء آلة من الأنواع المحددة"

AssetTypeAdmin.actions = [create_machine_from_type]


@admin.register(Technician)
class TechnicianAdmin(admin.ModelAdmin):
    list_display = ('user', 'specialization')
    search_fields = ('user__username', 'specialization')




class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'quantity')


class MaintenanceTaskInline(admin.TabularInline):
    model = MaintenanceTask
    extra = 1
    fields = ('task_id', 'title','machine_part', 'status', 'technician', 'scheduled_date')
    readonly_fields = ('task_id',)
    show_change_link = True

@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ('work_order_id', 'title', 'machine', 'status_badge', 'priority_badge', 'created_date', 'technician')
    list_filter = ('status', 'priority', 'created_date', 'technician')
    search_fields = ('title', 'work_order_id', 'machine__name')
    inlines = [MaintenanceTaskInline]
    date_hierarchy = 'created_date'
    ordering = ('-created_date',)
    fieldsets = (
        ('معلومات أساسية', {
            'fields': ('title', 'description', 'machine', 'location')
        }),
        ('التفاصيل الفنية', {
            'fields': ('technician', 'priority', 'estimated_duration', 'due_date')
        }),
        ('حالة الأمر', {
            'fields': ('status', 'completion_notes')
        }),
    )

    def display_machine(self, obj):
        return obj.machine.name if obj.machine else "Not Assigned"
    display_machine.short_description = 'Machine'

    def status_badge(self, obj):
        status_classes = {
            'open': 'warning',
            'in_progress': 'info',
            'completed': 'success',
            'closed': 'secondary'
        }
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            status_classes.get(obj.status, 'secondary'),
            obj.get_status_display()
        )
    status_badge.short_description = 'الحالة'

    def priority_badge(self, obj):
        priority_classes = {
            'low': 'success',
            'medium': 'warning',
            'high': 'danger',
            'critical': 'dark'
        }
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            priority_classes.get(obj.priority, 'secondary'),
            obj.get_priority_display()
        )
    priority_badge.short_description = 'الأولوية'

class TaskInventoryUsageInline(admin.TabularInline):
    model = TaskInventoryUsage
    extra = 1

@admin.register(MaintenanceTask)
class MaintenanceTaskAdmin(admin.ModelAdmin):
    list_display = ('task_id', 'title', 'work_order_link', 'status_badge', 'technician', 'scheduled_date')
    list_filter = ('status', 'technician', 'scheduled_date')
    search_fields = ('title', 'description', 'task_id', 'work_order__title')
    raw_id_fields = ('work_order', 'technician', 'machine_part')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    inlines = [TaskInventoryUsageInline]
    
    fieldsets = (
        ('معلومات أساسية', {
            'fields': ('title', 'description', 'work_order', 'machine_part')
        }),
        ('التفاصيل الفنية', {
            'fields': ('technician', 'instructions', 'scheduled_date')
        }),
        ('حالة المهمة', {
            'fields': ('status', 'completed_date')
        }),
        # تم إزالة قسم المواد المستخدمة من fieldsets
    )

    def work_order_link(self, obj):
        return format_html(
            '<a href="/admin/base/workorder/{}/change/">{}</a>',
            obj.work_order.work_order_id,
            obj.work_order.work_order_id
        )
    work_order_link.short_description = 'أمر العمل'

    def status_badge(self, obj):
        status_classes = {
            'pending': 'warning',
            'in_progress': 'info',
            'completed': 'success',
            'failed': 'danger'
        }
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            status_classes.get(obj.status, 'secondary'),
            obj.get_status_display()
        )
    status_badge.short_description = 'الحالة'