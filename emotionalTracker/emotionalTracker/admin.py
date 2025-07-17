from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from django.core.exceptions import ValidationError
from .models import (
    EmotionType,
    Cluster,
    Entity,
    Department,
    Service,
    Collaborator,
    Emotion
)


@admin.register(EmotionType)
class EmotionTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'emoticon', 'degree', 'created_at')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ('name', 'cluster', 'description', 'created_at')
    list_filter = ('cluster',)
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'entity', 'description', 'created_at')
    list_filter = ('entity',)
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'description', 'created_at')
    list_filter = ('department',)
    search_fields = ('name',)
    ordering = ('name',)

    def get_department_name(self, obj):
        return obj.department.name if obj.department else 'No Department'
    get_department_name.short_description = 'Department'


class CollaboratorAdmin(UserAdmin):
    # form = CollaboratorAdminForm
    model = Collaborator
    list_display = ('email_address', 'first_name', 'last_name', 'role', 'manager',
                    'service', 'department', 'entity', 'cluster',
                    'is_active', 'is_staff',
                    )

    def get_service_name(self, obj):
        return obj.service.name if obj.service else 'No service'
    get_service_name.short_description = 'Service'

    def get_department_name(self, obj):
        return obj.department.name if obj.department else 'No department'
    get_department_name.short_description = 'Département'

    def get_entity_name(self, obj):
        return obj.entity.name if obj.entity else 'No entity'
    get_entity_name.short_description = 'Entity'

    def get_cluster_name(self, obj):
        return obj.cluster.name if obj.cluster else 'No cluster'
    get_cluster_name.short_description = 'Cluster'

    list_filter = ('role', 'service', 'is_active', 'is_staff')
    search_fields = ('email_address', 'first_name', 'last_name')
    ordering = ('email_address',)

    fieldsets = (
        (None, {'fields': ('email_address', 'password')}),
        ('Informations personnelles', {'fields': ('first_name', 'last_name', 'role', 'manager', 'service', 'department', 'entity', 'cluster')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),  # , 'groups', 'user_permissions'
        # ('Dates importantes', {'fields': ()}),
    )

    add_fieldsets = (
        (None, {
                'classes': ('Wide',),
                'fields': ('email_address', 'first_name', 'last_name', 'role', 'manager',
                    'cluster', 'entity', 'department', 'service', 'password1', 'password2',
                    'is_active', 'is_staff', 'is_superuser',
                ),
            }
        ),
    )
    autocomplete_fields = ['manager', 'service', 'department', 'entity', 'cluster']
    filter_horizontal = ('groups', 'user_permissions',)



admin.site.register(Collaborator, CollaboratorAdmin)


@admin.register(Emotion)
class EmotionAdmin(admin.ModelAdmin):
    list_display = (
        'emotion_type', 'emotion_degree', 'collaborator', 'date', 'week_number', 'month', 'year', 'half_day',
        'calculate_date_period'
    )
    list_filter = ('emotion_type', 'half_day', '_date_period', 'month', 'year') # removed date_period or change it into _date_period
    search_fields = ('collaborator__first_name', 'collaborator__last_name', 'emotion_type__name')
    ordering = ('-date',)

    def calculate_date_period(self, obj):
        """
        Method to display the dynamically calculated date_period in admin
        """

        return obj.date_period
    calculate_date_period.short_description = "Date Period"



