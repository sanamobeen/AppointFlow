from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.exceptions import ValidationError

from .models import Business, BusinessWorkingHours, BusinessRegistrationRequest

User = get_user_model()


def _generate_business_slug(name):
    base_slug = slugify(name)[:200] or 'business'
    slug = base_slug
    suffix = 2
    while Business.objects.filter(slug=slug).exists():
        slug = f'{base_slug}-{suffix}'
        suffix += 1
    return slug


def _get_or_create_owner(request):
    user = User.objects.filter(email=request.owner_email).first()
    if user is None:
        # password=None creates an unusable password; the owner claims
        # the account via password reset.
        user = User.objects.create_user(
            email=request.owner_email,
            password=None,
            first_name=request.owner_full_name.split(' ', 1)[0],
            last_name=request.owner_full_name.split(' ', 1)[1]
            if ' ' in request.owner_full_name
            else '',
            phone=request.owner_phone,
        )
    return user


@transaction.atomic
def approve_registration_request(registration_request, reviewed_by):
    if registration_request.status != BusinessRegistrationRequest.Status.PENDING:
        raise ValidationError(
            'Only pending registration requests can be approved.'
        )

    owner = _get_or_create_owner(registration_request)
    business = Business.objects.create(
        name=registration_request.business_name,
        slug=_generate_business_slug(registration_request.business_name),
        category=registration_request.category,
        owner=owner,
        phone=registration_request.business_phone,
        email=registration_request.business_email,
        city=registration_request.city,
        address=registration_request.address,
        description=registration_request.description,
        photo=registration_request.photo,
    )
    BusinessWorkingHours.objects.bulk_create(
        [
            BusinessWorkingHours(
                business=business,
                weekday=hours.weekday,
                is_closed=hours.is_closed,
                opening_time=hours.opening_time,
                closing_time=hours.closing_time,
            )
            for hours in registration_request.working_hours.all()
        ]
    )

    registration_request.status = BusinessRegistrationRequest.Status.APPROVED
    registration_request.reviewed_at = timezone.now()
    registration_request.reviewed_by = reviewed_by
    registration_request.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])
    return business


@transaction.atomic
def reject_registration_request(registration_request, reviewed_by, admin_notes=''):
    if registration_request.status != BusinessRegistrationRequest.Status.PENDING:
        raise ValidationError(
            'Only pending registration requests can be rejected.'
        )

    registration_request.status = BusinessRegistrationRequest.Status.REJECTED
    registration_request.reviewed_by = reviewed_by
    registration_request.admin_notes = admin_notes
    registration_request.save(
        update_fields=['status', 'reviewed_by', 'admin_notes']
    )
    return registration_request
