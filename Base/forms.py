from django import forms
from .models import InventoryItem, AssetType, User ,WorkOrder, MaintenanceTask ,Technician ,Machine,TaskInventoryUsage,MachineFailure
from django.contrib.auth.forms import UserCreationForm,UserChangeForm
from django.utils import timezone
from datetime import datetime


class UserRegistrationRequestForm(UserCreationForm):
    JOB_TITLE_CHOICES = [
        ('inventory_manager', 'Inventory Manager'),
        ('maintenance_manager', 'Maintenance Manager'),
        ('maintenance_technician', 'Maintenance Technician'),
        ('regular_employee', 'Regular Employee'),
    ]
    job_title = forms.ChoiceField(choices=JOB_TITLE_CHOICES, required=True, label='Job Title', widget=forms.Select(attrs={'class': 'form-select'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}))
    first_name = forms.CharField(
        max_length=30,
        label="First Name",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter first name'})
    )   
    last_name = forms.CharField(
        max_length=30,
        label="Last Name",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter last name'})
    )
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'job_title', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter username'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter first name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter last name'}),
            'job_title': forms.Select(attrs={'class': 'form-select', 'placeholder': 'Select job title'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter password'})
        self.fields['password2'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'})



class AddItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ['name', 'description', 'serial_number', 'quantity', 'location', 'minimumStockLevel']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter item name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter item description'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter serial number'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter quantity'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter location'}),
            'minimumStockLevel': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter minimum stock level'})
        }


class AddAssetForm(forms.ModelForm):
    description = forms.CharField(
        label="Description",
        required=False,  
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'id': 'failureReasonInput',
            'placeholder': 'Enter asset description',
        }),
        initial="", 
    )
    class Meta:
        model = AssetType
        fields = ['name', 'description', 'parent']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter asset name'}),
            'parent': forms.Select(attrs={'class': 'form-select', 'placeholder': 'Select parent asset (optional)'})
        }

    def __init__(self, *args, **kwargs):
        # استخراج assetid من kwargs إذا كان موجوداً
            self.assetid = kwargs.pop('assetid', None)
            super().__init__(*args, **kwargs)


class UserForm(forms.ModelForm):
    ROLE_CHOICES = [
        ('inventory_manager', 'Inventory Manager'),
        ('maintenance_manager', 'Maintenance Manager'),
        ('maintenance_technician', 'Maintenance Technician'),
        ('regular_employee', 'Regular Employee'),
    ]
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role' ]
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class CustomUserCreationForm(UserCreationForm):
    ROLE_CHOICES = [    
        ('inventory_manager', 'Inventory Manager'),
        ('maintenance_manager', 'Maintenance Manager'),
        ('maintenance_technician', 'Maintenance Technician'),
        ('regular_employee', 'Regular Employee'),
    ]
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True)
    
    # إضافة حقول الفني
    existing_specialization = forms.ChoiceField(
        choices=[],
        required=False,
        label="Choose existing specialization",
        widget=forms.Select(attrs={'class': 'form-control', 'style': 'margin-bottom: 15px;', 'placeholder': 'Select specialization'})
    )
    new_specialization = forms.CharField(
        required=False,
        label="Or enter a new specialization",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter new specialization', 'style': 'margin-top: 10px;'})
    )
    phonenumber = forms.IntegerField(required=False, label="Phone Number", widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter phone number'}))
    notes = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter notes'}), required=False, label="Notes")
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'password1', 'password2', 'email', 'role']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter username'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter first name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter last name'}),
            'password1': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter password'}),
            'password2': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}),
            'role': forms.Select(attrs={'class': 'form-select', 'onchange': "toggleTechnicianFields()", 'placeholder': 'Select role'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # تعيين كلاس bootstrap لكل حقل يدويًا لضمان ظهور التنسيق
        for field_name in ['username', 'first_name', 'last_name', 'password1', 'password2', 'email', 'phonenumber']:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs['class'] = 'form-control'
        if 'role' in self.fields:
            self.fields['role'].widget.attrs['class'] = 'form-select'
        if 'notes' in self.fields:
            self.fields['notes'].widget.attrs['class'] = 'form-control'
            self.fields['notes'].widget.attrs['rows'] = 3
        # إعداد خيارات التخصصات الموجودة
        from .models import Technician
        specializations = Technician.objects.values_list('specialization', flat=True).distinct()
        self.fields['existing_specialization'].choices = [('', '-- Select --')] + [(s, s) for s in specializations]
        # جعل الحقول غير مطلوبة افتراضيًا
        self.fields['existing_specialization'].required = False
        self.fields['new_specialization'].required = False
        self.fields['phonenumber'].required = False
        self.fields['notes'].required = False

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        if role == 'maintenance_technician':
            existing = cleaned_data.get('existing_specialization')
            new = cleaned_data.get('new_specialization')
            if existing and new:
                raise forms.ValidationError("يرجى اختيار تخصص موجود أو إدخال تخصص جديد وليس كليهما.")
            if not existing and not new:
                raise forms.ValidationError("يجب اختيار تخصص موجود أو إدخال تخصص جديد.")
            if existing:
                cleaned_data['specialization'] = existing
            else:
                cleaned_data['specialization'] = new
            if not cleaned_data.get('phonenumber'):
                self.add_error('phonenumber', 'This field is required for technicians')
        return cleaned_data

class CustomUserChangeForm(UserChangeForm):
    ROLE_CHOICES = [
        ('inventory_manager', 'Inventory Manager'),
        ('maintenance_manager', 'Maintenance Manager'),
        ('maintenance_technician', 'Maintenance Technician'),
        ('regular_employee', 'Regular Employee'),
    ]
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
        }


class WorkOrderForm(forms.ModelForm):
    due_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date','class': 'form-control', 'placeholder': 'Select due date'}))
    
    class Meta:
        model = WorkOrder
        fields = ['title', 'description', 'machine', 'technician', 'due_date', 
                 'priority', 'location', 'estimated_duration']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class':'form-control', 'placeholder': 'Enter work order description'}),
            'estimated_duration': forms.TextInput(attrs={'placeholder': 'Enter estimated duration (e.g. HH:MM:SS)', 'class': 'form-control'}),
            'machine': forms.Select(attrs={'class': 'form-select', 'placeholder': 'Select machine'}),
            'title': forms.TextInput(attrs={'class':'form-control', 'placeholder': 'Enter work order title'}),
            'technician': forms.Select(attrs={'class': 'form-select', 'placeholder': 'Select technician'}),
            'priority' : forms.Select(attrs={'class': 'form-select', 'placeholder': 'Select priority'}),
            'location' : forms.TextInput(attrs={'class':'form-control', 'placeholder': 'Enter location (optional)'}),   
        }

class MaintenanceTaskForm(forms.ModelForm):
    scheduled_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date','class': 'form-control'}), required=False)
    
    class Meta:
        model = MaintenanceTask
        fields = ['title', 'description', 'technician', 'scheduled_date', 
                 'machine_part', 'instructions']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3 , 'class':'form-control'}),
            'instructions': forms.Textarea(attrs={'rows': 3 , 'class':'form-control'}),
            'machine_part': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class':'form-control'}),
            'technician': forms.Select(attrs={'class': 'form-select'}),
           
        }

        def __init__(self, *args, **kwargs):
        # استخراج work_order من kwargs إذا كان موجوداً
            self.work_order = kwargs.pop('work_order', None)
            super().__init__(*args, **kwargs)
            
            # تصفية أجزاء الماكينة إذا كان work_order موجوداً وله ماكينة
            if self.work_order and self.work_order.machine:
                self.fields['machine_part'].queryset = Machine.objects.filter(
                    parent_machine=self.work_order.machine
                )
            else:
                self.fields['machine_part'].queryset = Machine.objects.none()

class StatusUpdateForm(forms.ModelForm):
    failure_reason = forms.CharField(
        label="Failure Reason",
        required=False,  
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'id': 'failureReasonInput',
        }),
        initial="", 
    )

    class Meta:
        model = MaintenanceTask
        fields = ['status', 'failure_reason']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-select',
                'id': 'statusSelect',
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        failure_reason = cleaned_data.get('failure_reason', '').strip()

        if status == 'failed':
            if not failure_reason:
                self.add_error('failure_reason', 'This field is required when status is failed')
            cleaned_data['failure_reason'] = failure_reason

        return cleaned_data
    

class InventoryUsageForm(forms.ModelForm):
    class Meta:
        model = TaskInventoryUsage
        fields = ['item', 'quantity_used' , 'quantity_reserved']
        widgets = {
            'item': forms.Select(attrs={'class': 'form-select'}),
            'quantity_used': forms.NumberInput(attrs={'class': 'form-control'}),
            'quantity_reserved': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # عرض فقط العناصر المتاحة
        self.fields['item'].queryset = InventoryItem.objects.filter(quantity__gt=0)
        
    def clean_quantity_used(self):
        quantity_used = self.cleaned_data['quantity_used']
        item = self.cleaned_data.get('item')
        
        if item and quantity_used > item.quantity:
            raise forms.ValidationError(
                f"الكمية المتاحة فقط {item.quantity} من {item.name}"
            )
        return quantity_used


class TechnicianForm(forms.ModelForm):
    existing_specialization = forms.ChoiceField(
        choices=[],
        required=False,
        label="Choose an existing specialization",
        widget=forms.Select(attrs={'class': 'form-control', 'placeholder': 'Select specialization'})
    )
    new_specialization = forms.CharField(
        required=False,
        label="Or enter a new specialization",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter new specialization'})
    )

    class Meta:
        model = Technician
        fields = ['phonenumber', 'notes']
        widgets = {
            'phonenumber': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        specializations = Technician.objects.values_list('specialization', flat=True).distinct()
        
        self.fields['existing_specialization'] = forms.ChoiceField(
            choices=[('', '-- Select Existing --')] + [(s, s) for s in specializations],
            required=False,
            widget=forms.Select(attrs={'class': 'form-control'})
        )
        
        self.fields['new_specialization'] = forms.CharField(
            required=False,
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter new specialization...'
            })
        )
        
        self.fields['phonenumber'].required = True
        self.fields['phonenumber'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'e.g. +963933123456'
        })

    def clean(self):
        cleaned_data = super().clean()
        existing = cleaned_data.get('existing_specialization')
        new = cleaned_data.get('new_specialization')
        
        # التحقق من التخصص
        if existing and new:
            raise forms.ValidationError("Please choose either existing or new specialization, not both.")
        elif not existing and not new:
            raise forms.ValidationError("You must provide a specialization.")
        else:
            cleaned_data['specialization'] = existing if existing else new
        
        # التحقق من رقم الهاتف
        if not cleaned_data.get('phonenumber'):
            raise forms.ValidationError("Phone number is required for technicians.")
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.specialization = self.cleaned_data.get('specialization')
        if commit:
            instance.save()
        return instance
    
class CategorySelectionForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=AssetType.objects.filter(parent=None),
        label="Categorys",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'category-select'
        })
    )

class MachineCreationForm(forms.ModelForm):
    image = forms.ImageField(required=False)
    description = forms.CharField(
        label="Description",
        required=False,  
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'id': 'failureReasonInput',
        }),
        initial="", 
    )
    class Meta:
        model = Machine
        fields = ['name', 'serial_number', 'purchase_date' ,'location', 'image' , 'description' ]
        widgets = {
                'purchase_date' : forms.DateInput(attrs={'autocomplete': 'date' , 'value': timezone.now().strftime('%Y-%m-%d')})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get('purchase_date'):
            self.initial['purchase_date'] = datetime.now().strftime('%Y-%m-%d')

class MachineForm(forms.ModelForm):
    image = forms.ImageField(required=False)
    description = forms.CharField(
        label="Description",
        required=False,  
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'id': 'failureReasonInput',
        }),
        initial="", 
    )
    class Meta:
        model = Machine
        fields = ['name', 'serial_number', 'purchase_date', 'location' ,'parent_machine', 'image' , 'description']
        widgets = {
                'purchase_date' : forms.DateInput(attrs={'autocomplete': 'date' , 'value': timezone.now().strftime('%Y-%m-%d')})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['serial_number'].required = False

class MachineFailureForm(forms.ModelForm):
    class Meta:
        model = MachineFailure
        fields = ['title', 'description', 'machine', 'priority']  # Removed failure_date
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Failure Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Failure Description'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['machine'].queryset = Machine.objects.filter(parent_machine=None)
        self.fields['priority'].initial = 'medium'