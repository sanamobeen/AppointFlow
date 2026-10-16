from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils.text import slugify


class Weekday(models.IntegerChoices):
    MONDAY = 0, 'Monday'
    TUESDAY = 1, 'Tuesday'
    WEDNESDAY = 2, 'Wednesday'
    THURSDAY = 3, 'Thursday'
    FRIDAY = 4, 'Friday'
    SATURDAY = 5, 'Saturday'
    SUNDAY = 6, 'Sunday'


class BusinessCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'business categories'

    def __str__(self):
        return self.name


class BusinessRegistrationRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    business_name = models.CharField(max_length=200)
    category = models.ForeignKey(
        BusinessCategory,
        on_delete=models.PROTECT,
        related_name='registration_requests',
    )
    business_phone = models.CharField(max_length=20)
    business_email = models.EmailField(blank=True)
    city = models.CharField(max_length=100)
    address = models.TextField()
    description = models.TextField()
    photo = models.ImageField(upload_to='business-registration/', blank=True)
    owner_full_name = models.CharField(max_length=200)
    owner_email = models.EmailField()
    owner_phone = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_business_requests',
    )
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.business_name} ({self.get_status_display()})'


class BusinessRegistrationHours(models.Model):
    Weekday = Weekday

    registration_request = models.ForeignKey(
        BusinessRegistrationRequest,
        on_delete=models.CASCADE,
        related_name='working_hours',
    )
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    is_closed = models.BooleanField(default=False)
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ['weekday']
        constraints = [
            models.UniqueConstraint(
                fields=['registration_request', 'weekday'],
                name='unique_registration_weekday',
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        is_closed=True,
                        opening_time__isnull=True,
                        closing_time__isnull=True,
                    )
                    | Q(
                        is_closed=False,
                        opening_time__isnull=False,
                        closing_time__isnull=False,
                        closing_time__gt=F('opening_time'),
                    )
                ),
                name='valid_registration_hours',
            ),
        ]

    def __str__(self):
        return f'{self.registration_request.business_name} - {self.get_weekday_display()}'


class Business(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    category = models.ForeignKey(
        BusinessCategory,
        on_delete=models.PROTECT,
        related_name='businesses',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_businesses',
    )
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    city = models.CharField(max_length=100)
    address = models.TextField()
    description = models.TextField()
    photo = models.ImageField(upload_to='businesses/', blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class BusinessWorkingHours(models.Model):
    Weekday = Weekday

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='working_hours',
    )
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    is_closed = models.BooleanField(default=False)
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ['weekday']
        constraints = [
            models.UniqueConstraint(
                fields=['business', 'weekday'],
                name='unique_business_weekday',
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        is_closed=True,
                        opening_time__isnull=True,
                        closing_time__isnull=True,
                    )
                    | Q(
                        is_closed=False,
                        opening_time__isnull=False,
                        closing_time__isnull=False,
                        closing_time__gt=F('opening_time'),
                    )
                ),
                name='valid_business_hours',
            ),
        ]

    def __str__(self):
        return f'{self.business.name} - {self.get_weekday_display()}'