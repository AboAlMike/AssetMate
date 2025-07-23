from turtle import title
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.dispatch import receiver
from mptt.models import MPTTModel, TreeForeignKey
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db.models.signals import post_save
from datetime import timedelta
from django.utils import timezone



class InventoryItem(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = 'Available'
        CRITICAL = 'Critical'
    itemId = models.AutoField(primary_key=True)
    serial_number = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    quantity = models.IntegerField(default=0)
    location = models.CharField(max_length=255)
    minimumStockLevel = models.IntegerField(default=0)
    description = models.TextField(
        blank=True,  
        null=True,  
        default='',  
     
    )
    
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.AVAILABLE,
        editable=False,  
        blank=True,
    )

    def save(self, *args, **kwargs):
        if self.quantity is not None and self.minimumStockLevel is not None:
            self.status = self.Status.AVAILABLE if self.quantity > self.minimumStockLevel else self.Status.CRITICAL
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"


class User(AbstractUser):
    ROLE_CHOICES = [
        ('pending', 'Pending Approval'),
        ('inventory_manager', 'Inventory Manager'),
        ('maintenance_manager', 'Maintenance Manager'),
        ('system_admin', 'System Admin'),
        ('maintenance_technician', 'Maintenance Technician'),
        ('regular_employee', 'Regular Employee'),
    ]

    JOB_TITLE_CHOICES = [
        ('inventory_manager', 'Inventory Manager'),
        ('maintenance_manager', 'Maintenance Manager'),
        ('maintenance_technician', 'Maintenance Technician'),
        ('regular_employee', 'Regular Employee'),
    ]

    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='pending')
    job_title = models.CharField(max_length=50,null=True, choices=JOB_TITLE_CHOICES, verbose_name='Job Title')
    last_activity = models.DateTimeField(null=True, blank=True)
    image = models.ImageField(upload_to='profile_pics/', default='profile_pics/default.jpg')

    def __str__(self):
        return self.username

    def is_technician(self):
        return hasattr(self, 'technician') or self.role == 'maintenance_technician'

    def is_online(self):
        if self.last_activity:
            return timezone.now() - self.last_activity < timedelta(minutes=5)
        return False

class AssetType(MPTTModel):
    assetid = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    level_indicator = models.CharField(max_length=100, blank=True, editable=False, default=0)
    is_template = models.BooleanField(default=True, verbose_name="Is Template")
    
    class MPTTMeta:
        order_insertion_by = ['name']
        verbose_name = "Asset Type"
        verbose_name_plural = "Asset Types"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.level_indicator = "• " * (self.level + 1)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.level_indicator}{self.name}"
    
    def create_machine_from_type(self, parent_machine=None, **kwargs):
        """إنشاء آلة من هذا النوع مع جميع الأجزاء الفرعية"""
        machine_data = {
            'asset_class': self,
            'name': self.name,
            'parent_machine': parent_machine, 
            'is_template': False,
        }
        

        for key, value in kwargs.items():
            if key not in machine_data:
                machine_data[key] = value
        
        machine = Machine.objects.create(**machine_data)
        

        for child in self.get_children():
            child_kwargs = {
                k: v for k, v in kwargs.items() 
                if k not in ['serial_number', 'parent_machine']
            }
            child.create_machine_from_type(
                parent_machine=machine,
                **child_kwargs
            )
        
        return machine

class Machine(models.Model):
    asset_class = models.ForeignKey(AssetType, on_delete=models.CASCADE, verbose_name="Asset Type", null=True)
    name = models.CharField(max_length=100, verbose_name="Machine name")
    serial_number = models.CharField(max_length=100, unique=True, verbose_name="serial number")
    description = models.TextField(blank=True)
    purchase_date = models.DateField()
    image = models.ImageField(upload_to='machine_images/', null=True, blank=True)
    location = models.CharField(max_length=100)
    parent_machine = models.ForeignKey('self', on_delete=models.CASCADE, 
                                     null=True, blank=True,
                                     related_name='child_machines')
    is_template = models.BooleanField(default=False)
    status_choices = [
        ('Operational', 'Operational'),
        ('Under Maintenance', 'Under Maintenance'),
        ('Out of Order', 'Out of Order'), 
        ('Retired', 'Retired'),
    ]
    status = models.CharField(max_length=20, choices=status_choices, default='Operational')

    class Meta:
        verbose_name = "Machine"
        verbose_name_plural = "Machines"
    
    def __str__(self):
        asset_name = self.asset_class.name if self.asset_class else "No Asset Class"
        return f"{asset_name} - {self.name}"
    
    def get_full_hierarchy(self):
        return {
            'machine': self,
            'children': [child.get_full_hierarchy() for child in self.child_machines.all()]
        }
    

class Technician(models.Model):
    Technicianid = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE,verbose_name="User",
        related_name='technician') 
    specialization = models.CharField(max_length=100,
        verbose_name="Specialization")
    phonenumber = models.IntegerField()
    notes = models.TextField(blank=True)


    def __str__(self):
        return f"{self.user.get_full_name()} - {self.specialization}"
    class Meta:
        verbose_name = "Technician"
        verbose_name_plural = "Technicians"



class WorkOrder(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('closed', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    work_order_id = models.AutoField(primary_key=True, verbose_name='Work Order ID')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    machine = models.ForeignKey(
        Machine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Machine"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_work_orders',
        null=True,  # السماح بقيم NULL
        blank=True  # السماح بأن يكون الحقل فارغاً في النماذج
    )    
    created_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField()
    technician = models.ForeignKey(Technician, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_work_orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    location = models.CharField(max_length=100,blank=True)
    estimated_duration = models.DurationField(null=True, blank=True)
    actual_duration = models.DurationField(null=True, blank=True)
    completion_notes = models.TextField(blank=True)
# Order by created_date
    class Meta:
        ordering = ['-created_date']
        
    def save(self, *args, **kwargs):
        if self.machine and not self.location:
            self.location = self.machine.location
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Work Order #{self.work_order_id}: {self.title}" + (f" - {self.machine.name}" if self.machine else "")



class MaintenanceTask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    task_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    technician = models.ForeignKey(Technician, on_delete=models.SET_NULL, null=True, blank=True)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='tasks')
    inventory_items = models.ManyToManyField(
        'InventoryItem',
        through='TaskInventoryUsage',
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    scheduled_date = models.DateField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    machine_part = models.ForeignKey(Machine, on_delete=models.CASCADE, null=True, blank=True)
    instructions = models.TextField(blank=True, null=True, verbose_name="Instructions")
    # تم إزالة safety_precautions

    class Meta:
        ordering = ['-created_at']
        
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.task_id}: {self.title}"



class TaskInventoryUsage(models.Model):
    USAGE_STATUS = [
        ('reserved', 'Reserved'),
        ('partially_used', 'Partially Used'),
        ('fully_used', 'Fully Used'),
        ('returned', 'Returned')
    ]
    task = models.ForeignKey('MaintenanceTask', on_delete=models.CASCADE)
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)
    quantity_reserved = models.PositiveIntegerField(default=0,verbose_name="Quantity Reserved" )
    quantity_used = models.PositiveIntegerField(
        default=0,
        verbose_name="Quantity Used"
    )
    status = models.CharField(
        max_length=15,
        choices=USAGE_STATUS,
        default='reserved'
    )
    used_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Task Inventory Usages"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.quantity_used} x {self.item.name} for {self.task.title}"
    

    
class MachineFailure(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    failure_date = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    work_order_created = models.BooleanField(default=False, verbose_name="Work Order Created")
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, 
                                 null=True, blank=True,
                                 related_name='reported_failures',
                                 verbose_name="Reported By")

    def __str__(self):
        return f"{self.title} - {self.machine.name}"
    
    class Meta:
        verbose_name = "Machine Failure"
        verbose_name_plural = "Machine Failures"

    
class WorkOrderClosingReport(models.Model):
    work_order = models.OneToOneField(WorkOrder, on_delete=models.CASCADE, related_name='closing_report')
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    closed_date = models.DateTimeField(auto_now_add=True)
    report_content = models.JSONField()  # لتخزين البيانات بشكل منظم
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Closing Report for {self.work_order.work_order_id}"



class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=100)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Notification for {self.user.username}: {self.message}'