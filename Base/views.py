from asyncio.log import logger
from django.forms import FloatField
from django.shortcuts import render, get_object_or_404, redirect
from .forms import UserRegistrationRequestForm
from django.http import HttpResponse, HttpResponseForbidden
from django.core.management import call_command
import io
from django.http import JsonResponse
from Base.models import ( 
    InventoryItem,
    AssetType,
    User,
    Technician, 
    WorkOrder, 
    MaintenanceTask,
    Machine,
    MachineFailure,
    TaskInventoryUsage, 
    WorkOrderClosingReport,
    Notification
)
from .forms import( 
    CustomUserCreationForm,
    UserForm,
    CustomUserChangeForm,
    TechnicianForm,
    InventoryUsageForm,
    StatusUpdateForm,
    MachineCreationForm,
    MachineForm,
    MachineFailureForm,
    AddItemForm,
    MaintenanceTaskForm,
    CategorySelectionForm,
    AddAssetForm,
    WorkOrderForm,
)
from django.contrib import messages
import json
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth import update_session_auth_hash,authenticate,login,logout
from django.contrib.auth.decorators import login_required,user_passes_test
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum, F, ExpressionWrapper, IntegerField, Count, Avg, Q,FloatField
from django.db.models.functions import TruncDate


def contact_view(request):
    return render(request, 'NiceAdmin/contact.html')

def about_view(request):
    return render(request, 'NiceAdmin/about.html')

def about_view_not_authenticated(request):
    return render(request, 'NiceAdmin/about_not_authenticated.html')

def notifications_view(request):
    # Mark all unread notifications as read
    request.user.notifications.filter(is_read=False).update(is_read=True)
    
    # Get all notifications to display on the page
    notifications = request.user.notifications.order_by('-created_at')
    return render(request, 'NiceAdmin/notifications.html', {'notifications': notifications})


@login_required
@user_passes_test(lambda u: u.role == 'system_admin')
def system_admin_dashboard(request):
    """Dashboard for System Admin: Shows user stats, system activity, health, and recent actions."""
    users = User.objects.all()
    active_users = sum(1 for u in users if u.is_online())
    inactive_users = sum(1 for u in users if not u.is_online())
    # 1. User Management Statistics
    users_report = {
        'total_users': User.objects.count(),
        'active_users': active_users,
        'inactive_users': inactive_users,
        'users_by_role': list(User.objects.values('role').annotate(count=Count('role')).order_by('-count')),
        'recent_users': User.objects.order_by('-date_joined')[:5],
        'technicians_count': Technician.objects.count(),
    }

    # 2. System Activity (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    activity_report = {
        'work_orders_last_30d': WorkOrder.objects.filter(created_date__gte=thirty_days_ago).count(),
        'failures_last_30d': MachineFailure.objects.filter(failure_date__gte=thirty_days_ago).count(),
        'activity_timeline': list(
            WorkOrder.objects
                .filter(created_date__gte=thirty_days_ago)
                .annotate(date=TruncDate('created_date'))
                .values('date')
                .annotate(count=Count('work_order_id'))
                .order_by('-date')[:10]
        ),
    }

    # 3. System Health
    health_report = {
        'critical_items': InventoryItem.objects.filter(status='Critical').count(),
        'out_of_order_machines': Machine.objects.filter(status='Out of Order').count(),
        'overdue_work_orders': WorkOrder.objects.filter(
            (Q(status='open') | Q(status='in_progress')),
            due_date__lt=timezone.now().date()
        ).count(),
        'unassigned_tasks': MaintenanceTask.objects.filter(technician__isnull=True).count(),
    }

    # 4. Recent Activities
    recent_activities = {
        'last_work_orders': WorkOrder.objects.select_related('machine', 'technician').order_by('-created_date')[:5],
        'last_failures': MachineFailure.objects.select_related('machine').order_by('-failure_date')[:5],
    }

    # Prepare data for charts
    chart_data = {
        'users_by_role': json.dumps(users_report['users_by_role']),
        'activity_timeline': json.dumps([
            {
                'date': item['date'].strftime('%Y-%m-%d') if item['date'] else '',
                'count': item['count']
            }
            for item in activity_report['activity_timeline']
        ]),
    }

    context = {
        'users_report': users_report,
        'activity_report': activity_report,
        'health_report': health_report,
        'recent_activities': recent_activities,
        'chart_data': chart_data,
        'current_month': timezone.now().strftime("%B %Y"),
        'dashboard_last_updated': timezone.now(),
        'users_by_role_labels': json.dumps([item['role'] or 'Unknown' for item in users_report['users_by_role']]) if users_report['users_by_role'] else json.dumps([]),
        'users_by_role_counts': json.dumps([item['count'] or 0 for item in users_report['users_by_role']]) if users_report['users_by_role'] else json.dumps([]),
        'activity_timeline_labels': json.dumps([item['date'].strftime('%Y-%m-%d') if item['date'] else '' for item in activity_report['activity_timeline']]) if activity_report['activity_timeline'] else json.dumps([]),
        'activity_timeline_counts': json.dumps([item['count'] or 0 for item in activity_report['activity_timeline']]) if activity_report['activity_timeline'] else json.dumps([]),
    }

    return render(request, 'NiceAdmin/system_admin_dashboard.html', context)


@login_required
def maintenance_manager_dashboard(request):
    # 1. تقارير الأعطال
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    failures_report = {
        'total_failures': MachineFailure.objects.count(),
        'critical_failures': MachineFailure.objects.filter(priority='critical').count(),
        'pending_failures': MachineFailure.objects.filter(work_order_created=False).count(),
        'recent_failures': MachineFailure.objects
                          .select_related('machine', 'reported_by')
                          .order_by('-failure_date')[:5],
        'failures_last_30_days': MachineFailure.objects
                                .filter(failure_date__gte=thirty_days_ago)
                                .count(),
        'failure_trends': list(MachineFailure.objects
                      .annotate(date=TruncDate('failure_date'))
                      .values('date')
                      .annotate(count=Count('id'))
                      .order_by('date')[:10])
    }

    # 2. تقارير أوامر العمل
    work_orders_report = {
        'recent_work_orders': WorkOrder.objects.select_related('machine', 'technician').order_by('-created_date')[:5],        'total_work_orders': WorkOrder.objects.count(),
        'open_work_orders': WorkOrder.objects.filter(status='open').count(),
        'in_progress_work_orders': WorkOrder.objects.filter(status='in_progress').count(),
        'overdue_work_orders': WorkOrder.objects.filter(
            (Q(status='open') | Q(status='in_progress')),
            due_date__lt=timezone.now().date()
        ).count(),
        'high_priority_orders': WorkOrder.objects.filter(priority='high').count(),
        'avg_completion_time': WorkOrder.objects
                              .filter(status='completed')
                              .aggregate(
                                  avg_time=Avg(
                                      F('actual_duration') or F('estimated_duration')
                                  )
                              ),
        'work_order_distribution': WorkOrder.objects
                                   .values('status')
                                   .annotate(count=Count('status'))
                                   .order_by('-count')
    }

    # 3. تقارير المهام
    tasks_report = {
        'pending_tasks': MaintenanceTask.objects.filter(status='pending').count(),
        'completed_tasks_this_month': MaintenanceTask.objects.filter(
            status='completed',
            completed_date__month=timezone.now().month
        ).count(),
        'tasks_by_technician': MaintenanceTask.objects
                              .filter(technician__isnull=False)
                              .values(
                                  'technician__user__username',
                                  'technician__specialization'
                              )
                              .annotate(
                                  total=Count('task_id'),
                                  completed=Count('task_id', filter=Q(status='completed'))
                              )
                              .order_by('-total')[:5],
        'task_completion_rate': MaintenanceTask.objects.aggregate(
            total=Count('task_id'),
            completed=Count('task_id', filter=Q(status='completed'))
        )
    }

    # 4. تقارير المخزون
    inventory_report = {
        'critical_items': InventoryItem.objects.filter(status='Critical').count(),
        'most_used_items': TaskInventoryUsage.objects
                          .values('item__name', 'item__quantity')
                          .annotate(
                              total_used=Sum('quantity_used'),
                              total_reserved=Sum('quantity_reserved')
                          )
                          .order_by('-total_used')[:5],
        'reserved_items': TaskInventoryUsage.objects.filter(status='reserved').count(),
        'inventory_status': {
            'total_items': InventoryItem.objects.count(),
            'available_items': InventoryItem.objects.filter(status='Available').count(),
            'critical_items': InventoryItem.objects.filter(status='Critical').count()
        }
    }

    # 5. تقارير الفنيين
    technicians_report = {
        'top_performers': Technician.objects
                            .annotate(
                                completed_tasks=Count(
                                    'assigned_work_orders__tasks',
                                    filter=Q(assigned_work_orders__tasks__status='completed')
                                )
                            )
                            .order_by('-completed_tasks')[:3],
        'technicians_workload': Technician.objects
                               .annotate(
                                   current_tasks=Count(
                                       'assigned_work_orders__tasks',
                                       filter=Q(assigned_work_orders__tasks__status='in_progress')
                               ))
                               .values(
                                   'user__username',
                                   'specialization',
                                   'current_tasks'
                               ),
        'technician_efficiency': Technician.objects
                                .annotate(
                                    completed=Count(
                                        'assigned_work_orders__tasks',
                                        filter=Q(assigned_work_orders__tasks__status='completed')
                                ))
                                .annotate(
                                    total=Count('assigned_work_orders__tasks')
                                )
                                .filter(total__gt=0)
                                .annotate(
                                    efficiency=ExpressionWrapper(
                                        F('completed') * 100 / F('total'),
                                        output_field=FloatField()
                                    )
                                )
                                .order_by('-efficiency')[:5]
    }

    # 6. تقارير الإغلاق
    closing_reports = {
        'recent_closures': WorkOrderClosingReport.objects
                           .select_related('work_order', 'closed_by')
                           .order_by('-closed_date')[:5],
        'closure_rate': {
            'completed': WorkOrder.objects.filter(status='completed').count(),
            'total': WorkOrder.objects.count()
        },
        'average_resolution_time': WorkOrderClosingReport.objects
                                  .annotate(
                                      resolution_time=F('closed_date') - F('work_order__created_date')
                                  )
                                  .aggregate(
                                      avg_resolution=Avg('resolution_time')
                                  )
    }

    failures_report['failure_trends'] = [
        {
            'date': trend['date'].strftime('%Y-%m-%d'),
            'count': trend['count']
        }
        for trend in failures_report['failure_trends']
    ]
    
    work_orders_report['work_order_distribution'] = list(
        work_orders_report['work_order_distribution'].values('status', 'count')
    )
    # تجميع كل التقارير
    context = {
        'failures_report': failures_report,
        'work_orders_report': work_orders_report,
        'tasks_report': tasks_report,
        'inventory_report': inventory_report,
        'technicians_report': technicians_report,
        'closing_reports': closing_reports,
        'current_month': timezone.now().strftime("%B %Y"),
        'dashboard_last_updated': timezone.now()
        
    }
 

    return render(request, 'NiceAdmin/maintenance_manager_dashboard.html', context)


@login_required
def warehouse_dashboard(request):
    try:
        items = InventoryItem.objects.all()
        critical_items = InventoryItem.objects.annotate(
            deficit=ExpressionWrapper(
                F('minimumStockLevel') - F('quantity'),
                output_field=IntegerField()
            )
        ).filter(quantity__lte=F('minimumStockLevel'))

        used_items_list = list(TaskInventoryUsage.objects.filter(
            quantity_used__gt=0
        ).values('item__name').annotate(
            total_used=Sum('quantity_used')
        ).order_by('-total_used')[:5])

        returned_items_list = list(TaskInventoryUsage.objects.filter(
            status='returned'
        ).values('item__name').annotate(
            total_returned=Sum('quantity_reserved')
        ).order_by('-total_returned')[:5])
        
        # تحضير بيانات جميع المواد للرسم البياني
        all_items_list = list(InventoryItem.objects.values('name', 'quantity').order_by('-quantity')[:10])  # عرض أهم 10 مواد حسب الكمية
        
        return render(request, 'NiceAdmin/warehouse_dashboard.html', {
            'items': items,
            'critical_items': critical_items,
            'used_items': used_items_list,
            'returned_items': returned_items_list,
            # Pass JSON strings for JavaScript initialization
            'all_items_json': json.dumps(all_items_list),  # تم تغييرها لاستخدام json.dumps بدلاً من serializers
            'used_items_json': json.dumps(used_items_list),
            'returned_items_json': json.dumps(returned_items_list),
            'current_month': timezone.now().strftime("%B %Y")
        })
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return render(request, 'NiceAdmin/warehouse_dashboard.html', {
            'critical_items': [],
            'used_items': [],
            'returned_items': [],
            'all_items_json': json.dumps([]),
            'used_items_json': json.dumps([]),
            'returned_items_json': json.dumps([]),
            'current_month': timezone.now().strftime("%B %Y")
        })


def update_task_status_techDash(request, task_id):
    task = get_object_or_404(MaintenanceTask, pk=task_id)
    task.status = request.POST.get('status')
    if task.status == 'completed':
        task.completed_date = timezone.now()
    task.save()
    messages.success(request, f'Task status updated to {task.status}')
    return redirect('technician-dashboard')


def add_inventory_to_task_techDash(request, task_id):
    task = get_object_or_404(MaintenanceTask, pk=task_id)
    
    if request.method == 'POST':
        form = InventoryUsageForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    item = form.cleaned_data['item']
                    quantity_reserved = form.cleaned_data['quantity_reserved']
                    quantity_used = form.cleaned_data.get('quantity_used', 0)
                    
                    # التحقق من توفر الكمية
                    if item.quantity < quantity_reserved:
                        messages.error(request, 'Not enough quantity available in inventory')
                        return redirect('technician-dashboard')
                    
                    if quantity_used > quantity_reserved:
                        messages.error(request, 'Used quantity cannot exceed reserved quantity')
                        return redirect('technician-dashboard')
                    
                    # خصم الكمية المحجوزة من المخزون
                    item.quantity -= quantity_reserved
                    item.save()
                    
                    # تسجيل الاستخدام
                    TaskInventoryUsage.objects.create(
                        task=task,
                        item=item,
                        quantity_reserved=quantity_reserved,
                        quantity_used=quantity_used,
                        status='reserved' if quantity_used == 0 else 'partially_used'
                    )
                    
                    messages.success(request, f'Successfully added {quantity_reserved} of {item.name} (Used: {quantity_used})')
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
        else:
            error_msg = "Form errors: "
            for field, errors in form.errors.items():
                error_msg += f"{field}: {', '.join(errors)} "
            messages.error(request, error_msg)
    
    return redirect('technician-dashboard')



@login_required
@user_passes_test(lambda u: u.role == 'inventory_manager')
def get_inventory_data(request):
    # This view is already returning JSON, so no changes needed here.
    try:
        used_items = TaskInventoryUsage.objects.filter(
            quantity_used__gt=0
        ).values('item__name').annotate(
            total_used=Sum('quantity_used')
        ).order_by('-total_used')[:5]
        
        returned_items = TaskInventoryUsage.objects.filter(
            status='returned'
        ).values('item__name').annotate(
            total_returned=Sum('quantity_reserved')
        ).order_by('-total_returned')[:5]
        
        return JsonResponse({
            'used_items': list(used_items),
            'returned_items': list(returned_items)
        })
    except Exception as e: # Catch a specific exception and log it
        logger.error(f"Error fetching inventory data: {str(e)}")
        return JsonResponse({
            'used_items': [{'item__name':'لا يوجد بيانات','total_used':0}],
            'returned_items': [{'item__name':'لا يوجد بيانات','total_returned':0}]
        })


@login_required
def technician_dashboard(request):
    if request.user.role == 'maintenance_technician':
        technician = request.user.technician

        # تصفية أوامر العمل والمهام
        work_orders = WorkOrder.objects.filter(
            technician=technician
        ).order_by('-created_date')

        tasks = MaintenanceTask.objects.filter(
            technician=technician
        ).select_related('work_order').order_by('-created_at')

        # معالجة تحديث الحالة (POST request)
        if request.method == 'POST' and 'update_status' in request.POST:
            task_id = request.POST.get('task_id')
            task = get_object_or_404(MaintenanceTask, pk=task_id)
            form = StatusUpdateForm(request.POST, instance=task)
            
            if form.is_valid():
                updated_task = form.save(commit=False)
                if updated_task.status == 'completed':
                    updated_task.completed_date = timezone.now()
                updated_task.save()
                messages.success(request, f'Task #{task.task_id} status updated successfully')
                return redirect('technician-dashboard')

        # معالجة إضافة المواد من المستودع (POST request)
        if request.method == 'POST' and 'add_inventory' in request.POST:
            task_id = request.POST.get('task_id')
            task = get_object_or_404(MaintenanceTask, pk=task_id)
            form = InventoryUsageForm(request.POST)
            
            if form.is_valid():
                inventory_usage = form.save(commit=False)
                inventory_usage.task = task
                item = inventory_usage.item
                
                # التحقق من توفر الكمية
                if item.quantity >= inventory_usage.quantity_used:
                    inventory_usage.save()
                    item.quantity -= inventory_usage.quantity_used
                    item.save()
                    messages.success(request, f'Consumed {inventory_usage.quantity_used} of {item.name}')
                else:
                    messages.error(request, f'Quantity not available in the warehouse for {item.name}!')
                return redirect('technician-dashboard')

        # تهيئة النماذج الفارغة لعرضها
        status_form = StatusUpdateForm()
        inventory_form = InventoryUsageForm()

        context = {
            'work_orders': work_orders,
            'tasks': tasks,
            'today': timezone.now().date(),
            'StatusUpdateForm': status_form,  # نموذج تحديث الحالة
            'inventory_form': inventory_form,  # نموذج إضافة المواد
        }
        return render(request, 'NiceAdmin/technician_dashboard.html', context)


@login_required
def indexPage(request):
    if request.user.role == 'maintenance_technician':        
        return redirect('technician-dashboard')
    elif request.user.role == 'inventory_manager':
        return redirect('warehouse-dashboard')
    elif request.user.role == 'regular_employee':
        return redirect('view-failures')
    elif request.user.role == 'maintenance_manager':
         return redirect('maintenance-manager-dashboard')
    elif request.user.role == 'system_admin':
         return redirect('system-admin-dashboard')
    elif request.user.role == 'pending':
         return render(request, 'NiceAdmin/pending_user.html')
    else:
        return render(request,'NiceAdmin/index.html')


@login_required
def logout_view(request):
    logout(request)
    return redirect('loginpage')


def is_system_admin(user):
    return user.is_authenticated and user.role == 'system_admin'


@user_passes_test(is_system_admin)
def pending_accounts_list(request):
    pending_users = User.objects.filter(role='pending')
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        new_role = request.POST.get('role')
        user_to_update = User.objects.get(id=user_id)
        user_to_update.role = new_role
        user_to_update.save()
        messages.success(request, f"Account for {user_to_update.username} approved and role changed to {new_role}.")
        return redirect('pending-accounts-list')
    forms_list = [(user, UserForm(instance=user)) for user in pending_users]
    return render(request, 'NiceAdmin/pending_accounts_list.html', {'forms_list': forms_list})



def register_request_view(request):
    if request.method == 'POST':
        form = UserRegistrationRequestForm(request.POST)
        job_title = request.POST.get('job_title', '')
        is_technician = job_title == 'maintenance_technician'
        technician_form = TechnicianForm(request.POST) if is_technician else TechnicianForm()
        if form.is_valid() and (not is_technician or technician_form.is_valid()):
            user = form.save(commit=False)
            user.role = 'pending'
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.is_active = True
            user.save()
            if is_technician:
                technician = technician_form.save(commit=False)
                technician.user = user
                technician.save()
            messages.success(request, 'Registration successful!')

            admins = User.objects.filter(role='system_admin')
            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    title = 'New User Registration Request',
                    message = f'Somebody trying to join AssetMate as {job_title}, check him now...'

                )

            return redirect('loginpage')
    else:
        form = UserRegistrationRequestForm()
        technician_form = TechnicianForm()
        job_title = ''
    return render(request, 'NiceAdmin/register_request.html', {
        'form': form,
        'technician_form': technician_form,
        'job_title': job_title,
    })
    

def loginpage(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        try:
            user = User.objects.get(username=username)
        except:
            messages.error(request, "User does not exist")
        
        user = authenticate(request, username=username , password=password)
        if user is not None:
            login(request,user)
            return redirect('indexPage')
        else:
            messages.error(request, 'Username Or Password does not exist')

    return render (request,'NiceAdmin/pages-login.html')



# ****************************************** Inventory Tracking views *****************************************************************************************************
@login_required
def Inventory_Tracking(request):
    items = InventoryItem.objects.all()
    return render(request, 'NiceAdmin/Inventory_Tracking.html', {'InventoryItem': items})


@login_required
def edit_item(request, item_id):
    item = get_object_or_404(InventoryItem, itemId=item_id)
    
    if request.method == 'POST':
        try:
            item.name = request.POST['name']
            item.quantity = int(request.POST.get('quantity', 0))
            item.description = request.POST.get('description', '')
            item.location = request.POST.get('location', '')
            item.minimumStockLevel = int(request.POST.get('minimumStockLevel', 0))
            item.serial_number = request.POST.get('serial_number', '')
            item.save()
            messages.success(request, 'item successfully updated')
            return redirect('Inventory_Tracking')
            
        except Exception as e:
            messages.error(request, f' error: {str(e)}')
    
    return render(request, 'NiceAdmin/Edit_item.html', {'item': item})


@login_required
def info_item(request, item_id):
    item = get_object_or_404(InventoryItem, itemId=item_id)
    return render(request, 'NiceAdmin/info_item.html', {'item': item})


@login_required
def delete_item(request, item_id):
    if request.method == 'POST':
        item = get_object_or_404(InventoryItem, itemId=item_id) 
        item.delete()
        messages.success(request, 'item deleted successfully')
        admins = User.objects.filter(role='system_admin')
        for admin in admins:
                Notification.objects.create(
                    user=admin,
                    title = 'Item Deleted',
                    message = f'{item.name} has been deleted from inventory...'

                )
    return redirect('Inventory_Tracking')


@login_required
def add_item(request):
    if request.method == 'POST':
        form = AddItemForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'item successfully added!')
            admins = User.objects.filter(role='system_admin')
            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    title = 'New Item Added',
                    message = f'New item added to inventory, check it now...'

                )
            return redirect('Inventory_Tracking')
        else:
            messages.success(request, "You did not filled all the requested fields")
    else:
        form = AddItemForm()
    return render(request, 'NiceAdmin/Add_item.html', {'form': form})

# ****************************************** Asset Management views *****************************************************************************************************

def Asset_Management(request):
    assets = AssetType.objects.all() 
    return render(request, 'NiceAdmin/asset_list.html', {'assets': assets})


def edit_asset(request, asset_id):
    asset = get_object_or_404(AssetType, assetid=asset_id)    
    if request.method == 'POST':
        try:
            asset.name = request.POST['name']
            asset.description = request.POST.get('description', '')
            asset.save()
            messages.success(request, 'Asset Category successfully updated')
            return redirect('asset-list')
            
        except Exception as e:
            messages.error(request, f' error: {str(e)}')
    
    return render(request, 'NiceAdmin/edit_asset.html', {'asset': asset})


def info_asset(request, asset_id):
    asset = get_object_or_404(AssetType, assetid=asset_id)    
    return render(request, 'NiceAdmin/info_asset.html', {'asset': asset})


def delete_asset(request, asset_id):
    if request.method == 'POST':
        asset = get_object_or_404(AssetType, assetid=asset_id) 
        asset.delete()
        messages.success(request, 'Asset deleted successfully')
    return redirect('asset-list')


def add_asset(request):
    if request.method == 'POST':
        form = AddAssetForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Asset Category successfully added!')
            return redirect('asset-list')
        else:
            messages.success(request, "You did not filled all the requested fields")
    else:
        form = AddAssetForm()
    return render(request, 'NiceAdmin/add_asset.html', {'form': form})


def add_asset_child(request, parent_id):
    parent = get_object_or_404(AssetType, assetid=parent_id)
    if request.method == 'POST':
        form = AddAssetForm(request.POST)
        if form.is_valid():
            child = form.save(commit=False)
            child.parent = parent  
            child.save()
            return redirect('asset-list')
    return render(request, 'NiceAdmin/add_asset_child.html', {'parent': parent})


def category_info(request, asset_id):
    asset = get_object_or_404(AssetType, assetid=asset_id)
    return render(request, 'NiceAdmin/category_info.html', {'asset': asset})


def get_asset_children(request, pk):
    asset = AssetType.objects.get(pk=pk)
    children = asset.get_children()
    data = [{
        'assetid': child.assetid,
        'name': child.name,
        'description': child.description
    } for child in children]
    return JsonResponse(data, safe=False)


def asset_list(request):
    assets = AssetType.objects.all()
    return render(request, 'asset_list.html', {'assets': assets})


# ****************************************** Users Management views *****************************************************************************************************

@login_required
def user_info_view(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    return render(request, 'NiceAdmin/user_info.html', {'user': user})

@login_required
def user_list(request):
        users = User.objects.all()
        return render(request, 'NiceAdmin/users_list.html', {'users': users})


def user_create(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = form.cleaned_data['role']
            user.save()
            
            # إذا كان المستخدم فنيًا، أنشئ سجل Technician
            if user.role == 'maintenance_technician':
                Technician.objects.create(
                    user=user,
                    specialization=form.cleaned_data['specialization'],
                    phonenumber=form.cleaned_data['phonenumber'],
                    notes=form.cleaned_data['notes']
                )
                maintenance_manager = User.objects.filter(role='maintenance_manager')
                for manager in maintenance_manager:
                    Notification.objects.create(
                    user=manager,
                    title = 'New Technician',
                    message = f'{user.username} join AssetMate as technician, check him now...'
                )
            
            messages.success(request, 'User created successfully!')
            return redirect('user-list')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'NiceAdmin/user_add.html', {
        'form': form,
        'technician_fields_required': False  # سيتم التحكم به عبر JavaScript
    })

def user_update(request, pk):
    user = get_object_or_404(User, pk=pk) 
    
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=user) 
        if form.is_valid():
            form.save()
            messages.success(request, 'User successfully updated!')
            return redirect('user-list')
        else:
            messages.error(request, 'Erorr')
    else:
        form = CustomUserChangeForm(instance=user)
    
    return render(request, 'NiceAdmin/user_update.html', {'form': form, 'user': user})


def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'User deleted successfully!')
        return redirect('user-list')
    return render(request, 'admin/users/delete.html', {'user': user})


def user_deny_account(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'User deleted successfully!')
        return redirect('pending-accounts-list')
    return render(request, 'admin/users/delete.html', {'user': user})


@login_required


@login_required
@user_passes_test(lambda u: u.role == 'system_admin')
def system_backup(request):
    if request.method == 'POST':
        buffer = io.StringIO()
        call_command('dumpdata', stdout=buffer)
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename=backup.json'
        return response
    return HttpResponseForbidden('Invalid method.')


@login_required
@user_passes_test(lambda u: u.role == 'system_admin')
def system_restore(request):
    if request.method == 'POST':
        try:
            backup_file = request.FILES.get('backup_file')
            if not backup_file:
                messages.error(request, ' Please upload a backup file first.')
                return redirect('system-admin-dashboard')

            if not backup_file.name.endswith('.json'):
                messages.error(request, ' Please upload a backup file with .json extension.')
                return redirect('system-admin-dashboard')
            import tempfile, os

            with tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='wb') as tmp_file:
                for chunk in backup_file.chunks():
                    tmp_file.write(chunk)
                tmp_file_path = tmp_file.name
            try:
                call_command('loaddata', tmp_file_path)
                messages.success(request, 'System restored successfully!')
            finally:
                os.remove(tmp_file_path)
        except Exception as e:
            messages.error(request, f'Error restoring system: {str(e)}')
        return redirect('system-admin-dashboard')
    return HttpResponseForbidden('Invalid method.')


def profile_page_view(request):
    user = request.user
    password_errors = None
    password_success = None
    if request.method == 'POST':
        if request.POST.get('password_change') == '1':
            old_password = request.POST.get('old_password', '')
            new_password1 = request.POST.get('new_password1', '')
            new_password2 = request.POST.get('new_password2', '')
            if not user.check_password(old_password):
                password_errors = 'Old password is incorrect.'
            elif new_password1 != new_password2:
                password_errors = 'New passwords do not match.'
            elif len(new_password1) < 8:
                password_errors = 'New password must be at least 8 characters.'
            else:
                user.set_password(new_password1)
                user.save()
                password_success = 'Password changed successfully! Please use the new password next time.'
                return redirect('loginpage')
        if request.method == 'POST' and request.POST.get('delete_image') == '1':
                if user.image and user.image.name != 'profile_pics/default.jpg':
                    user.image.delete(save=False)
                    user.image = 'profile_pics/default.jpg'
                    user.save()
                    messages.success(request, 'Profile picture deleted successfully!')
                else:
                    messages.info(request, 'No profile picture to delete.')
        else:
            first_name = request.POST.get('firstName', '').strip()
            last_name = request.POST.get('lastName', '').strip()
            email = request.POST.get('email', '').strip()
            changed = False
            if user.first_name != first_name:
                user.first_name = first_name
                changed = True
            if user.last_name != last_name:
                user.last_name = last_name
                changed = True
            if user.email != email:
                user.email = email
                changed = True
            if 'image' in request.FILES:
                user.image = request.FILES['image']
                changed = True
            if changed:
                user.save()
                messages.success(request, 'Profile updated successfully!')
            else:
                messages.info(request, 'No changes detected.')
            return redirect('profile_page')
    return render(request, 'NiceAdmin/profile_page.html', {'user': user, 'password_errors': password_errors, 'password_success': password_success})

def change_password(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = PasswordChangeForm(user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  
            return redirect('user-list')
    else:
        form = PasswordChangeForm(user)
    return render(request, 'NiceAdmin/change_password.html', {'form': form})

def admin_set_password_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Password changed successfully!')
            return redirect('user-info', user.id)
    else:
        form = SetPasswordForm(user)
    return render(request, 'NiceAdmin/admin_set_password.html', {'form': form, 'user': user})

# ****************************************** WorkOrder views *****************************************************************************************************

def technician_list(request):
    technicians = Technician.objects.all()
    specializations = Technician.objects.values_list('specialization', flat=True).distinct()
    return render(request, 'NiceAdmin/technician_list.html', {'technicians': technicians , 'specializations': specializations})

# 2. إنشاء أمر عمل جديد

def tech_info (request, technician_id):
    technician = get_object_or_404(Technician, pk=technician_id)
    return render(request, 'NiceAdmin/tech_info.html',{'technician': technician})

# 3. عرض تفاصيل أمر عمل


# 4. تحديث حالة أمر العمل (بواسطة الفني)



# 5. إضافة مهمة صيانة



# 6. طلب مواد من المخزن (بواسطة الفني)


# 7. عرض أوامر العمل المخصصة للفني

def technician_work_orders(request, tech_pk):
    technician = get_object_or_404(Technician, pk=tech_pk)
    work_orders = technician.view_assigned_work_orders()
    return render(request, 'technicians/work_orders.html', {
        'technician': technician,
        'work_orders': work_orders
    })


def delete_Tech(request, tech_id):
    if request.method == 'POST':
        asset = get_object_or_404(Technician, Technicianid=tech_id) 
        asset.delete()
        messages.success(request, 'Technician deleted successfully')
    return redirect('technician-list')


def edit_technician(request, technician_id):
    technician = get_object_or_404(Technician, pk=technician_id)
    # أو Technician.objects.values_list('specialization', flat=True).distinct() إذا كنت تستخدم حقل نصي
    
    if request.method == 'POST':
        # معالجة البيانات المرسلة من النموذج
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phonenumber')
        specialization = request.POST.get('specialization')
        notes = request.POST.get('notes')
        
        try:
            # تحديث بيانات المستخدم (User)
            user = technician.user
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.phone = phone
            user.save()
            
            # تحديث بيانات الفني (Technician)
            technician.phonenumber = phone
            technician.specialization = specialization
            technician.notes = notes
          
            
            technician.save()
            
            messages.success(request, "Technician updated successfully!")
            return redirect('technician-list')
            
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
    
    # إذا كانت الطريقة GET أو حدث خطأ
    return render(request, 'NiceAdmin/edit_technician.html', {
        'technician': technician,
      
    })


def tech_create(request):
    if request.method == 'POST':
        form = TechnicianForm(request.POST)
        if form.is_valid():
            try:
                technician = form.save()
                messages.success(request, 'technician added successfully')
                return redirect('technician-list')
            except Exception as e:
                messages.error(request, f'saving error: {str(e)}')
        else:
            print("Forms error:", form.errors)  
    else:
        form = TechnicianForm()
    return render(request, 'NiceAdmin/tech_add.html', {'form': form})

#********************************************************************************

def create_machine_from_type(request, type_id):
    asset_type = get_object_or_404(AssetType, assetid=type_id)
    
    if request.method == 'POST':
        form = MachineForm(request.POST)
        if form.is_valid():
            try:
                # إنشاء الآلة الرئيسية مع جميع الأجزاء الفرعية
                machine = asset_type.create_machine_from_type(
                    serial_number=form.cleaned_data['serial_number'],
                    purchase_date=form.cleaned_data['purchase_date'],
                    location=form.cleaned_data['location'],
                    status=form.cleaned_data['status']
                )
                messages.success(request, f'Machine {machine.name} created successfully with all parts!')
                return redirect('asset_list', machine_id=machine.id)
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
    else:
        form = MachineForm()
    
    return render(request, 'NiceAdmin/machin_add.html', {
        'asset_type': asset_type,
        'form': form,
        'components': asset_type.get_descendants()
    })

def select_category(request):
    if request.method == 'POST':
        form = CategorySelectionForm(request.POST)
        if form.is_valid():
            category_id = form.cleaned_data['category'].assetid
            return redirect('create_machines', category_id=category_id)
    else:
        form = CategorySelectionForm()
    
    return render(request, 'NiceAdmin/selectasset.html', {'form': form})


def create_machines(request, category_id):
    category = get_object_or_404(AssetType, assetid=category_id)
    
    if request.method == 'POST':
        form = MachineCreationForm(request.POST, request.FILES)
        if form.is_valid():
            # إنشاء الأصل الرئيسي
            main_machine = form.save(commit=False)
            main_machine.asset_class = category 
            main_machine.save()
            
            # إنشاء الأجزاء الفرعية تلقائياً
            create_child_machines(category, main_machine)
            
            messages.success(request, 'Asset created successfully with all parts!')
            admins = User.objects.filter(role='system_admin')
            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    title = 'New Machine Added',
                    message = f'New machine added to inventory, check it now...'

                )
            return redirect('machine_hierarchy')
    else:
        form = MachineCreationForm(initial={'name': category.name})
    
    return render(request, 'NiceAdmin/machin_add.html', {
        'form': form,
        'category': category
    })

def create_child_machines(category, parent_machine):
    for child_category in category.get_children():
        child_machine = Machine.objects.create(
            asset_class=child_category,  # استخدام asset_class هنا أيضاً
            name=child_category.name,
            serial_number=f"{parent_machine.serial_number}-{child_category.assetid}",
            parent_machine=parent_machine,
            status=parent_machine.status,
            location = parent_machine.location,
            purchase_date=parent_machine.purchase_date
        )
        create_child_machines(child_category, child_machine)


def machine_hierarchy(request):
    machines = Machine.objects.filter(parent_machine__isnull=True)
    Asset_class = Machine.objects.values_list('asset_class__name', flat=True).distinct()
    return render(request, 'NiceAdmin/machin_table.html', {'machines': machines ,'Asset_class': Asset_class})


def delete_Machine(request, pk):
    if request.method == 'POST':
        asset = get_object_or_404(Machine, pk=pk) 
        asset.delete()
        messages.success(request, 'machine deleted successfully')
        admins = User.objects.filter(role='system_admin')
        for admin in admins:
            Notification.objects.create(
                user=admin,
                title = 'Machine Deleted',
                message = f'{asset.name} has been deleted from machine list...'

            )
    return redirect('machine_hierarchy')


def edit_machine(request, pk):
    machine = get_object_or_404(Machine, pk=pk)
    
    if request.method == 'POST':
        image = request.FILES.get('image')
        name = request.POST.get('name')
        status = request.POST.get('status')
        location = request.POST.get('location')
        description = request.POST.get('description')
        
        try:
            machine.name = name
            machine.status = status
            machine.location = location
            machine.description = description
            if 'image' in request.FILES:
                if machine.image:
                    machine.image.delete(save=False)
                machine.image = request.FILES['image'] 
            machine.save()
            
            messages.success(request, f'{machine.name} updated successfully!')
            return redirect('machine_hierarchy')
            
        except Exception as e:
            messages.error(request, f'error: {str(e)}')
            return render(request, 'NiceAdmin/machine_edit.html', {
                'machine': machine,
                'error': str(e)
            })
    
    return render(request, 'NiceAdmin/machine_edit.html', {
        'machine': machine,
        'is_parent': machine.child_machines.exists()
    })


def info_machine(request, pk):
    machine = get_object_or_404(Machine, pk=pk)            
    return render(request, 'NiceAdmin/machine_info.html', {
        'machine': machine,
        'is_parent': machine.child_machines.exists()
    })


def add_machine_child_(request, parent_id):
    parent = get_object_or_404(Machine, pk=parent_id)
    if request.method == 'POST':
        form = MachineForm(request.POST)
        if form.is_valid():
            child = form.save(commit=False)
            child.parent = parent  
            child.save()
            return redirect('asset-list')
    return render(request, 'NiceAdmin/add_machine_child.html', {'parent': parent})



def add_machine_child(request, parent_id):
    parent_machine = get_object_or_404(Machine, pk=parent_id)
    
    if request.method == 'POST':
        form = MachineForm(request.POST, request.FILES)
        print(request.POST)  # لتصحيح الأخطاء
        if form.is_valid():
            try:
                child = form.save(commit=False)
                child.parent_machine = parent_machine
                
                if not child.serial_number:
                    last_child = Machine.objects.filter(parent_machine=parent_machine).order_by('-id').first()
                    new_number = 1 if not last_child else int(last_child.serial_number.split('-')[-1]) + 1
                    child.serial_number = f"{parent_machine.serial_number}-{new_number}"
                
                child.save()
                messages.success(request, f'{child.name} added successfully!')
                return redirect('machine_hierarchy')
                
            except Exception as e:
                messages.error(request, f'error: {str(e)}')
                print("Error:", str(e))  # لتصحيح الأخطاء
        else:
            print("Form errors:", form.errors)  # لتصحيح الأخطاء
    else:
        initial_data = {
            'status': parent_machine.status,
            'location': parent_machine.location,
            'purchase_date': parent_machine.purchase_date,
        }
        form = MachineForm(initial=initial_data)
    
    return render(request, 'NiceAdmin/add_machine_child.html', {
        'form': form,
        'parent_machine': parent_machine
    })


##################################################################################3



# إنشاء أمر عمل جديد
def work_order_create_(request):
    if request.method == 'POST':
        form = WorkOrderForm(request.POST)
        if form.is_valid():
            work_order = form.save(commit=False)
            work_order.created_by = request.user
            work_order.save()
            messages.success(request, f'Work order {work_order.work_order_id} created successfully!')
            return redirect('work_order_detail', pk=work_order.pk)
    else:
        form = WorkOrderForm()
    
    return render(request, 'work_orders/create.html', {'form': form})

# عرض تفاصيل أمر عمل مع مهامه


# تحديث أمر عمل
def work_order_update(request, pk):
    work_order = get_object_or_404(WorkOrder, pk=pk)
    
    if request.method == 'POST':
        form = WorkOrderForm(request.POST, instance=work_order)
        if form.is_valid():
            form.save()
            messages.success(request, f'Work order {work_order.work_order_id} updated successfully!')
            return redirect('work_order_detail', pk=pk)
    else:
        form = WorkOrderForm(instance=work_order)
    
    return render(request, 'work_orders/update.html', {'form': form, 'work_order': work_order})





def add_task_to_work_order(request, pk):
    work_order = get_object_or_404(WorkOrder, pk=pk)
    
    if request.method == 'POST':
        form = MaintenanceTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.work_order = work_order
            task.save()
            messages.success(request, 'Task added successfully!')
        else:
            messages.error(request, 'Error adding task. Please check the form.')
    
    return redirect('work-order-detail', pk=pk)

#************************************************************************************************************************


def work_order_create(request):
    if request.method == 'POST':
        try:
            # تحويل البيانات من النموذج
            due_date_str = request.POST.get('due_date')
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            
            # معالجة الحقول من نوع DurationField
            estimated_hours = request.POST.get('estimated_duration')
            estimated_duration = timedelta(hours=int(estimated_hours)) if estimated_hours else None
            
            actual_hours = request.POST.get('actual_duration')
            actual_duration = timedelta(hours=int(actual_hours)) if actual_hours else None
            
            # إنشاء أمر العمل جديد
            work_order = WorkOrder(
                title=request.POST.get('title'),
                description=request.POST.get('description'),
                machine_id=request.POST.get('machine'),
                technician_id=request.POST.get('technician') or None,
                due_date=due_date,
                priority=request.POST.get('priority'),
                status='open',
                estimated_duration=estimated_duration,
                actual_duration=actual_duration,
                created_by=request.user,
                location=request.POST.get('location'),
                completion_notes=request.POST.get('completion_notes', '')
            )
            work_order.save()
            
            messages.success(request, 'Work order created successfully!')
            admins = User.objects.filter(role='system_admin')
            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    title = 'New Work Order',
                    message = f'New work order has been created recently, check it now...'
                )
            if work_order.technician:
                Notification.objects.create(
                    user=work_order.technician.user,
                    title = 'New Work Order',
                    message = f'New work order has been assigned to you to supervise, check it now...'
                )
            return redirect('work_order_details', pk=work_order.pk)
            
        except ValueError as e:
            messages.error(request, f'Error in the entered values: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error during work order creation: {str(e)}')
    
    # جلب البيانات اللازمة للنموذج
    machines = Machine.objects.all()
    technicians = Technician.objects.all()
    
    # تعيين تاريخ الغد كتاريخ افتراضي
    default_due_date = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    context = {
        'machines': machines,
        'technicians': technicians,
        'default_due_date': default_due_date,
    }
    return render(request, 'NiceAdmin/work_order_create.html', context)



def work_order_detail(request, pk):
    work_order = get_object_or_404(WorkOrder, pk=pk)

    if request.method == 'POST':
        form = MaintenanceTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.work_order = work_order
            task.save()
            Notification.objects.create(
                user=task.technician.user,
                title='New Task Assigned',
                message=f'Task {task.title} has been assigned to you'
            )
            messages.success(request, 'Task added successfully')
            return redirect('work_order_details', pk=pk)
    else:
        form = MaintenanceTaskForm()
        # تصفية أجزاء الماكينة بعد إنشاء النموذج
        if work_order.machine:
            form.fields['machine_part'].queryset = Machine.objects.filter(
                parent_machine=work_order.machine
            )
        else:
            form.fields['machine_part'].queryset = Machine.objects.none()
    
    context = {
        'StatusUpdateForm': StatusUpdateForm,
        'work_order': work_order,
        'task_form': form,
   
        'inventory_form': InventoryUsageForm(),
    }
    return render(request, 'NiceAdmin/work_o_details.html', context)



def complete_work_order(request, pk):
    work_order = get_object_or_404(WorkOrder, pk=pk)
    work_order.status = 'completed'
    work_order.save()
    messages.success(request, 'Work order marked as completed')
    return redirect('work_order_details', pk=pk)

def add_maintenance_task(request, pk):
    work_order = get_object_or_404(WorkOrder, pk=pk)
    
    if request.method == 'POST':
        form = MaintenanceTaskForm(request.POST)
        if form.is_valid():
            try:
                task = form.save(commit=False)
                task.work_order = work_order
                
                # إذا كنت تحتاج لربط الماكينة بالمهمة
                if work_order.machine:
                    task.machine = work_order.machine
                task.save()
                messages.success(request, 'Task added successfully')
                Notification.objects.create(
                    user=task.technician.user,
                    title='New Task Assigned',
                    message=f'Task {task.title} has been assigned to you'
                    )
                return redirect('work_order_detail', pk=pk)
                
            except Exception as e:
                messages.error(request, f'Error in saving: {str(e)}')
        else:
            messages.error(request, 'Form data is not valid')
    else:
        form = MaintenanceTaskForm(initial={
            'scheduled_date': work_order.due_date or timezone.now().date()
        })
    
    context = {
        'work_order': work_order,
        'task_form': form,
        'inventory_form': InventoryUsageForm(),
    }
    return render(request, 'NiceAdmin/work_o_details.html', context)



def add_inventory_to_task(request, task_id):
    task = get_object_or_404(MaintenanceTask, pk=task_id)
    
    if request.method == 'POST':
        form = InventoryUsageForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    item = form.cleaned_data['item']
                    quantity_reserved = form.cleaned_data['quantity_reserved']
                    quantity_used = form.cleaned_data.get('quantity_used', 0)
                    
                    # التحقق من توفر الكمية
                    if item.quantity < quantity_reserved:
                        messages.error(request, 'الكمية غير متوفرة في المخزون')
                        return redirect('work-order-detail', pk=task.work_order.work_order_id)
                    
                    # خصم الكمية المحجوزة من المخزون
                    item.quantity -= quantity_reserved
                    item.save()
                    
                    # التحقق من أن الكمية المستخدمة لا تتجاوز المحجوزة
                    if quantity_used > quantity_reserved:
                        messages.error(request, 'الكمية المستخدمة أكبر من الكمية المحجوزة. يرجى حجز كمية إضافية أولاً.')
                        return redirect('work-order-detail', pk=task.work_order.work_order_id)

                    # تسجيل الاستخدام
                    TaskInventoryUsage.objects.create(
                        task=task,
                        item=item,
                        quantity_reserved=quantity_reserved,
                        quantity_used=quantity_used,
                        status='reserved' if quantity_used == 0 else 'partially_used'
                    )
                    inventory_manager = User.objects.filter(role='inventory_manager')
                    for inventory in inventory_manager:
                        Notification.objects.create(
                        user=inventory,
                        title = f'{item.name} Usage',
                        message = f'{item.name} usage in task {task.task_id}, check it now...'
                    )
                    
                    messages.success(request, 'تم تسجيل المواد بنجاح')
            except Exception as e:
                messages.error(request, f'حدث خطأ: {str(e)}')
        else:
            messages.error(request, 'Please provide a failure reason')
    
    return redirect('work-order-detail', pk=task.work_order.work_order_id)

def edit_work_order(request, pk):
    work_order = get_object_or_404(WorkOrder, pk=pk)
    
    if request.method == 'POST':
        form = WorkOrderForm(request.POST, instance=work_order)
        if form.is_valid():
            form.save()
            return redirect('work_order_details', pk=work_order.pk)
    else:
        form = WorkOrderForm(instance=work_order)
    
    context = {
        'form': form,
        'machines': Machine.objects.all(),
        'technicians': Technician.objects.all(),
        'work_order': work_order,
    }
    return render(request, 'NiceAdmin/work_order_edit.html', context)
    

def update_work_order_status(work_order):
    tasks = work_order.tasks.all()
    
    if not tasks.exists():
        work_order.status = 'open'
        work_order.save()
        return
    
    # إذا كانت جميع المهام مكتملة
    if all(task.status == 'completed' for task in tasks):
        new_status = 'completed'
        work_order.machine.status = 'Operational'
        work_order.machine.save()
    # إذا كانت أي مهمة فاشلة
    elif any(task.status == 'failed' for task in tasks):
        new_status = 'failed'

    # إذا كانت أي مهمة قيد التنفيذ
    elif any(task.status == 'in_progress' for task in tasks):
        new_status = 'in_progress'
        work_order.machine.status = 'Under Maintenance'
        work_order.machine.save()

    # إذا كانت جميع المهام معلقة
    else:
        new_status = 'open'
    
    # تحديث الحالة فقط إذا تغيرت
    if work_order.status != new_status:
        work_order.status = new_status
        work_order.save()
    
    maintenance_manager = User.objects.filter(role='maintenance_manager')
    for manager in maintenance_manager:
        Notification.objects.create(
            user=manager,
            title = f'Work Order {work_order.status}',
            message = f'Work Order {work_order.work_order_id} is {work_order.status}, check it now...'

        )


def update_task_status(request, task_id):
    task = get_object_or_404(MaintenanceTask, pk=task_id)
    
    if request.method == 'POST':
        form = StatusUpdateForm(request.POST, instance=task)
        if form.is_valid():
            task = form.save(commit=False)
            
            if task.status == 'completed':
                task.completed_date = timezone.now()
                task.completed_by = request.user

            elif task.status == 'failed' and not task.failure_reason:

                messages.error(request, 'Please provide a failure reason')
                return redirect('work-order-detail', pk=task.work_order.pk)
            
            task.save()
            update_work_order_status(task.work_order)
            maintenance_manager = User.objects.filter(role='maintenance_manager')
            for manager in maintenance_manager:
                Notification.objects.create(
                    user=manager,
                    title = f'Task {task.status}',
                    message = f'Task {task.task_id} is {task.status}, check it now...'

                    )
            return redirect('work-order-detail', pk=task.work_order.pk)
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                }, status=400)
            else:
                messages.error(request, 'Error updating status')
    else:
        form = StatusUpdateForm(instance=task)
    
    context = {
        'form': form,
        'task': task,
    }
    return render(request, 'NiceAdmin/work_o_details.html', context)

    

def delete_task(request, task_id):
    task = get_object_or_404(MaintenanceTask, task_id=task_id)
    work_order_pk = task.work_order.pk
    task.delete()
    messages.success(request, 'Task deleted successfully')
    return redirect('work-order-detail', pk=work_order_pk)


def close_work_order(request, work_order_id):
    work_order = get_object_or_404(WorkOrder, pk=work_order_id)
    
    if work_order.status == 'closed':
        messages.warning(request, 'Work order already closed')
        return redirect('work-order-detail', pk=work_order_id)
    
    with transaction.atomic():
        try:
            report_data = {
                'used_materials': [],
                'returned_materials': [],
                'tasks_summary': []
            }
            
            for task in work_order.tasks.all():
                task_summary = {
                    'task_id': task.task_id,
                    'status': task.get_status_display(),
                    'materials': []
                }
                
                for usage in task.taskinventoryusage_set.all():
                    material_data = {
                        'item_name': usage.item.name,
                        'reserved': usage.quantity_reserved,
                        'used': usage.quantity_used,
                        'status': usage.status
                    }
                    
                    if usage.quantity_used == 0:
                        remaining = usage.quantity_reserved
                        usage.item.quantity += remaining
                        usage.status = 'returned'
                        task_summary['materials'].append({
                            **material_data,
                            'action': f'Returned {remaining} to inventory'
                        })
                        inventory_manager = User.objects.filter(role='inventory_manager')
                        for inventory in inventory_manager:
                            Notification.objects.create(
                            user=inventory,
                            title = f'{item.name} Returned',
                            message = f'{item.name} returned to inventory from task {task.task_id}, check it now...'
                        )
                    
                    elif usage.quantity_used < usage.quantity_reserved:
                        remaining = usage.quantity_reserved - usage.quantity_used
                        usage.item.quantity += remaining
                        usage.status = 'partially_used'
                        task_summary['materials'].append({
                            **material_data,
                            'action': f'Returned {remaining} (Used {usage.quantity_used})'
                        })
                        inventory_manager = User.objects.filter(role='inventory_manager')
                        for inventory in inventory_manager:
                            Notification.objects.create(
                            user=inventory,
                            title = f'{item.name} Partially Returned',
                            message = f'{item.name} partially returned to inventory from task {task.task_id}, check it now...'
                        )
                    
                    else:
                        usage.status = 'fully_used'
                        task_summary['materials'].append({
                            **material_data,
                            'action': 'Fully used'
                        })
                    
                    usage.item.save()
                    usage.save()
                
                report_data['tasks_summary'].append(task_summary)
            
            work_order.status = 'closed'
            work_order.save()
            
            Notification.objects.create(
                user=work_order.technician.user,
                title='Work Order Closed',
                message=f'Work Order {work_order.work_order_id} has been closed, check it now...'
                )

            WorkOrderClosingReport.objects.create(
                work_order=work_order,
                closed_by=request.user,
                report_content=report_data,
                notes=request.POST.get('closing_notes', '')
            )
            
            messages.success(request, 'Work order closed successfully with detailed report')
            
        except Exception as e:
            messages.error(request, f'Error during closure: {str(e)}')
            return redirect('work-order-detail', pk=work_order_id)
    
    return redirect('work-order-detail', pk=work_order_id)
#****************************************************************************************************************

def report_machine_failure(request):
    if request.method == 'POST':
        form = MachineFailureForm(request.POST)
        if form.is_valid():

            failure = form.save(commit=False)
            failure.reported_by = request.user  # تعيين المستخدم الحالي
            failure.save() 
            
            machine = failure.machine
            machine.status = 'Out of Order'
            machine.save()
            maintenance_manager = User.objects.filter(role='maintenance_manager')
            for manager in maintenance_manager:
                Notification.objects.create(
                user=manager,
                title = 'New Failure',
                message = f'{failure.reported_by.username} reported a new failure, check it now...'
            )
            return redirect('view-failures')
    else:
        form = MachineFailureForm()
    
    return render(request, 'NiceAdmin/report_failure.html', {
        'form': form,
        'current_user': request.user  # يمكنك استخدامه في القالب إذا لزم الأمر
    })



def view_reported_failures(request):
    if request.user.role == 'regular_employee':  
        user_failures = MachineFailure.objects.filter(reported_by=request.user)
    else:
        user_failures = MachineFailure.objects.filter()

    failures = MachineFailure.objects.filter().order_by('-failure_date')

    # حساب الإحصائيات
    total_failures = user_failures.count()
    critical_failures = user_failures.filter(priority='critical').count()
    pending_failures = user_failures.filter(work_order_created=False).count()
    resolved_failures = user_failures.filter(work_order_created=True).count()
    
    return render(request, 'NiceAdmin/view_failures.html', {
        'failures': user_failures.order_by('-failure_date'),
        'total_failures': total_failures,
        'critical_failures': critical_failures,
        'pending_failures': pending_failures,
        'resolved_failures': resolved_failures,
        'failures': failures
    })

def edit_machine_failure(request, failure_id):
    failure = get_object_or_404(MachineFailure, id=failure_id)
    
    if request.method == 'POST':
        form = MachineFailureForm(request.POST, instance=failure)
        if form.is_valid():
            form.save()
            return redirect('view-failures')
    else:
        form = MachineFailureForm(instance=failure)
    
    return render(request, 'NiceAdmin/edit_failure.html', {
        'form': form,
        'failure': failure
    })


def create_work_order_from_failure(request, failure_id):
    failure = get_object_or_404(MachineFailure, id=failure_id)
    
    if request.method == 'POST':
        form = WorkOrderForm(request.POST)
        if form.is_valid():
            work_order = form.save(commit=False)
            work_order.failure_reference = failure
            if not work_order.machine and failure.machine:
                work_order.machine = failure.machine
            
            # تحديث حالة الآلة إلى "تحت الصيانة"
            if work_order.machine:
                work_order.machine.status = 'Under Maintenance'
                work_order.machine.save()
            
                
            work_order.save()
            
            failure.work_order_created = True
            failure.save()
            Notification.objects.create(
                user=failure.reported_by,
                title = 'Failure Under Maintenance',
                message = f'failure you reported is under maintenance...'
            )
            messages.success(request, f'Work order #{work_order.work_order_id} created successfully!')
            return redirect('work-order-detail', pk=work_order.work_order_id)
    else:
        initial_data = {
            'title': f"WO for Failure #{failure.id}",
            'description': failure.description,
            'machine': failure.machine,
            'priority': failure.priority,
            'location': failure.machine.location if failure.machine else None,
        }
        form = WorkOrderForm(initial=initial_data)
    
    return render(request, 'NiceAdmin/create_work_order_from_failure.html', {
        'form': form,
        'failure': failure,
    })

def work_order_list(request):
    # الحصول على جميع أوامر العمل مع إمكانية التصفية
    work_orders = WorkOrder.objects.all().order_by('-created_date')
    
    # تصفية حسب الحالة إذا كانت موجودة في الطلب
    status_filter = request.GET.get('status')
    if status_filter:
        work_orders = work_orders.filter(status=status_filter)
    
    # تصفية حسب الأولوية إذا كانت موجودة في الطلب
    priority_filter = request.GET.get('priority')
    if priority_filter:
        work_orders = work_orders.filter(priority=priority_filter)
    
    # التقسيم إلى صفحات
    paginator = Paginator(work_orders, 10)  # 10 أوامر عمل لكل صفحة
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'NiceAdmin/work_order_list.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
    })




def add_task_instructions(request, task_id):
    task = get_object_or_404(MaintenanceTask, task_id=task_id)
    
    if request.method == 'POST':
        instructions = request.POST.get('instructions')
        task.instructions = instructions
        task.save()
        messages.success(request, 'تم إضافة التعليمات بنجاح')
        return redirect('technician-dashboard')
    
    return render(request, 'NiceAdmin/add_instructions_modal.html', {'task': task})


def work_order_report(request, pk):
    work_order = get_object_or_404(WorkOrder, pk=pk)
    report = get_object_or_404(WorkOrderClosingReport, work_order=work_order)
    
    context = {
        'work_order': work_order,
        'report': report,
    }
    return render(request, 'NiceAdmin/work_order_report.html', context)


def work_order_report(request, pk):
    work_order = get_object_or_404(WorkOrder, pk=pk)
    report = get_object_or_404(WorkOrderClosingReport, work_order=work_order)
    
    context = {
        'work_order': work_order,
        'report': report,
    }
    return render(request, 'NiceAdmin/work_order_report.html', context)