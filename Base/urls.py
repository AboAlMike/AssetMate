from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('contact/', views.contact_view, name='contact'),
    path('about/', views.about_view, name='about'),
    path('about-not-authenticated/', views.about_view_not_authenticated, name='about_not_authenticated'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('index/',views.indexPage,name='indexPage'),

    path('',views.loginpage,name='loginpage'),

    path('Inventory_Tracking/',views.Inventory_Tracking,name='Inventory_Tracking'),

    path('edit-item/<int:item_id>/', views.edit_item, name='edit_item'),

    path('delete-item/<int:item_id>/', views.delete_item, name='delete_item'),

    path('info-item/<int:item_id>/', views.info_item, name='info_item'),

    path('add-item/', views.add_item, name='add_item'),
#*****************************************************************************************************
   
    path('assets/', views.Asset_Management, name='asset-list'),
    path('category_info/<int:asset_id>/', views.category_info, name='category_info'),
    path('assets/<int:pk>/children/', views.get_asset_children, name='asset-children'),
    path('info-asset/<int:asset_id>/', views.info_asset, name='info_asset'),
    path('add-asset/', views.add_asset, name='add_asset'),

    path('asset/<int:parent_id>/add_child/', views.add_asset_child, name='add_asset_child'),

    path('delete-asset/<int:asset_id>/', views.delete_asset, name='delete_asset'),

    path('edit-asset/<int:asset_id>/', views.edit_asset, name='edit_asset'),

#*****************************************************************************************************

    path('users/', views.user_list, name='user-list'),
    path('logout/', views.logout_view, name='logout'),
    path('register-request/', views.register_request_view, name='register-request'),
    path('pending-accounts-list/', views.pending_accounts_list, name='pending-accounts-list'),
    path('users/info/<int:user_id>/', views.user_info_view, name='user-info'),
    path('users/deny/<int:user_id>/', views.user_deny_account, name='user-deny-account'),
    path('profile/', views.profile_page_view, name='profile_page'),
    path('system-backup/', views.system_backup, name='system_backup'),
    path('users/create/', views.user_create, name='user-create'),

    path('users/update/<int:pk>/', views.user_update, name='user-update'),
    path('users/change-password/<int:pk>/', views.change_password, name='change-password'),
    path('users/admin-set-password/<int:pk>/', views.admin_set_password_view, name='admin-set-password'),

    path('users/delete/<int:pk>/', views.user_delete, name='user-delete'),

#*****************************************************************************************************
    path('technicians/', views.technician_list, name='technician-list'),
    path('technicians/<int:tech_pk>/work-orders/', views.technician_work_orders, name='technician-work-orders'),
    path('delete-tech/<int:tech_id>/', views.delete_Tech, name='delete_Tech'),
    path('tech/create/', views.tech_create, name='tech-add'),  
    path('tech-info/<int:technician_id>/', views.tech_info, name='tech_info'),
    path('edit-tech/<int:technician_id>/', views.edit_technician, name='edit_technician'),
    path('technicians/edit/<int:technician_id>/', views.edit_technician, name='edit-technician'),
    # أوامر العمل

    
    path('work-orders/<int:pk>/', views.work_order_detail, name='work-order-detail'),
    path('work-orders/<int:pk>/update-status/', views.update_work_order_status, name='update-work-order-status'),
    
    # مهام الصيانة
    path('work-orders/<int:work_order_pk>/add-task/', views.add_maintenance_task, name='add-maintenance-task'),

   
#*****************************************************************************************************

    path('type/<int:type_id>/create-machine/', views.create_machine_from_type, name='create_machine_from_type'),

    path('select-category/', views.select_category, name='select_category'),
    path('create-machines/<int:category_id>/', views.create_machines, name='create_machines'),
    path('machines/', views.machine_hierarchy, name='machine_hierarchy'),
    path('delete-machine/<int:pk>/', views.delete_Machine, name='delete_Machine'),
    path('machines/edit/<int:pk>/', views.edit_machine, name='edit_machine'),
    path('machines/info/<int:pk>/', views.info_machine, name='info_machine'),
    path('machines/add_child/<int:parent_id>/', views.add_machine_child, name='add_machine_child'),



    path('work-orders/', views.work_order_list, name='work-order-list'),
    path('work_order_create/', views.work_order_create, name='work_order_create'),
    path('work-orders/<int:pk>/', views.work_order_detail, name='work_order_details'),
    path('work-orders/<int:pk>/update/', views.work_order_update, name='work_order_update'),
    

    path('add_task_to_work_order/<int:pk>/', views.add_task_to_work_order, name='add_task_to_work_order'),

    path('work-orders/<int:pk>/', views.work_order_detail, name='work-order-detail'),
    path('work-orders/<int:pk>/complete/', views.complete_work_order, name='complete-work-order'),
    path('work-orders/<int:pk>/add-task/', views.add_maintenance_task, name='add-maintenance-task'),
    path('tasks/<int:task_id>/update-status/<str:status>/', views.update_task_status, name='update-task-status'),
    path('tasks/<int:task_id>/add-inventory/', views.add_inventory_to_task, name='add-inventory-to-task'),
    path('work-orders/<int:pk>/edit/', views.edit_work_order, name='work-order-edit'),

    path('tasks/<int:task_id>/update-status/', views.update_task_status, name='update-task-status'),
    path('tasks/<int:task_id>/delete/', views.delete_task, name='delete-task'),
    path('work-orders/<int:work_order_id>/close/', views.close_work_order, name='close-work-order'),

    path('report-failure/', views.report_machine_failure, name='report-failure'),
    path('view-failures/', views.view_reported_failures, name='view-failures'),
    path('edit-failure/<int:failure_id>/', views.edit_machine_failure, name='edit-failure'),
    path('failures/<int:failure_id>/create-work-order/', views.create_work_order_from_failure, name='create-work-order-from-failure'),




    path('technician/dashboard/', views.technician_dashboard, name='technician-dashboard'),
    path('task/<int:task_id>/update-status/', views.update_task_status_techDash, name='update-task-status-techDash'),
    path('task/<int:task_id>/add-inventory/', views.add_inventory_to_task_techDash, name='add-inventory-to-task-techDash'),
    path('task/<int:task_id>/add-instructions/', views.add_task_instructions, name='add-task-instructions'),
    path('work-orders/<int:pk>/report/', views.work_order_report, name='work-order-report'),

    
    path('inventory-data/', views.get_inventory_data, name='get_inventory_data'),
    path('warehouse/dashboard/', views.warehouse_dashboard, name='warehouse-dashboard'),


    path('maintenance/manager/dashboard/', views.maintenance_manager_dashboard, name='maintenance-manager-dashboard'),
    path('system-admin/dashboard/', views.system_admin_dashboard, name='system-admin-dashboard'),
    path('system-admin/system_restore/', views.system_restore, name='system_restore'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
