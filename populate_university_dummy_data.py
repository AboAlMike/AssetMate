# University Dummy Data Population Script (English)
# Run this script via: python manage.py shell < populate_university_dummy_data.py

from Base.models import InventoryItem, User, AssetType, Machine, Technician, WorkOrder, MaintenanceTask, MachineFailure
from django.utils import timezone
from django.contrib.auth.hashers import make_password
import random


# 1. AssetType

# 2. InventoryItem
locations = [
    "Computer Lab", "University Library", "Physics Lab", "Admin Office", "Lecture Hall 1", "Lecture Hall 2", "Equipment Store"
]
for i in range(15):
    InventoryItem.objects.get_or_create(
        serial_number=f"ITEM-{i+1:03}",
        name=f"Item {i+1} - {locations[i%len(locations)]}",
        defaults={
            'quantity': random.randint(5, 30),
            'location': locations[i%len(locations)],
            'minimumStockLevel': random.randint(2, 10),
            'description': f"Item {i+1} description",
            'status': "Available"
        }
    )

# 3. Users
roles = ["system_admin", "inventory_manager", "maintenance_manager", "maintenance_technician", "regular_employee"]
users = []
for i in range(15):
    u, _ = User.objects.get_or_create(
        username=f"user{i+1}",
        defaults={
            'password': make_password(f"password{i+1}"),
            'role': roles[i%len(roles)],
            'job_title': roles[i%len(roles)].replace('_', ' ').title(),
            'last_activity': timezone.now(),
        }
    )
    users.append(u)

# 4. Technicians (first 15 users as technicians)
technicians = []
for i in range(15):
    t, _ = Technician.objects.get_or_create(
        user=users[i],
        defaults={
            'specialization': f"Specialist in Item {i+1}",
            'phonenumber': f"0551{i+1:07}",
            'notes': f"Technician specialized in Item {i+1}"
        }
    )
    technicians.append(t)

from datetime import datetime

machines = []
for i in range(15):
    inv_item = InventoryItem.objects.get(itemId=i+1)
    m, _ = Machine.objects.get_or_create(
        serial_number=f"MACH-{i+1:03}",
        name=f"Machine {i+1}",
        location=inv_item.location,
        status="Operational",
        purchase_date=datetime.now(),  # إضافة تاريخ الشراء
        asset_class=None  # احذف أو عدل هذا السطر إذا كان الحقل مطلوباً
    )
    machines.append(m)

# 6. WorkOrders
from datetime import datetime, timedelta

work_orders = []
for i in range(15):
    wo, _ = WorkOrder.objects.get_or_create(
        title=f"Maintenance Work Order for Item {i+1}",
        created_by=users[i],
        defaults={
            'description': f"Issue reported in Item {i+1}",
            'status': "open",
            'priority': "medium",
            'technician': technicians[i],
            'due_date': datetime.now() + timedelta(days=7),  # إضافة تاريخ استحقاق بعد أسبوع
        }
    )
    work_orders.append(wo)

# 7. MaintenanceTasks
for i in range(15):
    MaintenanceTask.objects.get_or_create(
        title=f"Maintenance Task for Item {i+1}",
        technician=technicians[i],
        work_order=work_orders[i],
        defaults={
            'description': f"Repair Item {i+1}",
            'status': "pending",
            'instructions': "Please inspect the device carefully before operation."
        }
    )

# 8. MachineFailures
for i in range(15):
    MachineFailure.objects.get_or_create(
        machine=machines[i],
        title=f"Failure in Item {i+1}",
        reported_by=users[i],
        defaults={
            'description': f"The device is not functioning properly, instance {i+1}",
            'priority': "medium",
        }
    )

print("Dummy university data added successfully!")
