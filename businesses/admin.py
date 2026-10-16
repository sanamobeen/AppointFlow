from django.contrib import admin

from .models import (
    Business,
    BusinessCategory,
    BusinessRegistrationHours,
    BusinessRegistrationRequest,
    BusinessWorkingHours,
)


class BusinessRegistrationHoursInline(admin.TabularInline):
    model = BusinessRegistrationHours
    extra = 0


class BusinessWorkingHoursInline(admin.TabularInline):
    model = BusinessWorkingHours
    extra = 0


@admin.register(BusinessCategory)
class BusinessCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(BusinessRegistrationRequest)
class BusinessRegistrationRequestAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'owner_full_name', 'city', 'status', 'submitted_at')
    list_filter = ('status', 'category', 'city')
    search_fields = ('business_name', 'owner_full_name', 'owner_email', 'owner_phone')
    readonly_fields = ('submitted_at', 'created_at', 'updated_at')
    inlines = (BusinessRegistrationHoursInline,)


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'city', 'owner', 'is_active')
    list_filter = ('is_active', 'category', 'city')
    search_fields = ('name', 'owner__email')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    inlines = (BusinessWorkingHoursInline,)