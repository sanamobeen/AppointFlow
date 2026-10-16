import json
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.test import APIClient

from .models import (
    Business,
    BusinessCategory,
    BusinessRegistrationHours,
    BusinessRegistrationRequest,
    BusinessWorkingHours,
)
from .services import approve_registration_request, reject_registration_request

User = get_user_model()


def working_hours_payload():
    hours = []
    for weekday in range(7):
        if weekday == 6:
            hours.append({'weekday': weekday, 'is_closed': True})
        else:
            hours.append({
                'weekday': weekday,
                'is_closed': False,
                'opening_time': '09:00',
                'closing_time': '17:00',
            })
    return hours


def registration_payload(category_id):
    return {
        'business_name': 'Smile Dental',
        'category': category_id,
        'business_phone': '+923001234567',
        'business_email': 'hello@smiledental.example',
        'city': 'Lahore',
        'address': '10 Main Road',
        'description': 'Family dental clinic.',
        'owner_full_name': 'Ali Khan',
        'owner_email': 'ali@example.com',
        'owner_phone': '+923009876543',
        'working_hours': working_hours_payload(),
    }


class RegistrationAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = BusinessCategory.objects.create(
            name='Dental Clinic',
            slug='dental-clinic',
        )
        self.payload = registration_payload(self.category.id)

    def test_categories_lists_active_categories_only(self):
        BusinessCategory.objects.create(
            name='Inactive Category',
            slug='inactive-category',
            is_active=False,
        )

        response = self.client.get('/api/business-categories/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Dental Clinic')

    def test_registration_request_is_created_pending_with_all_hours(self):
        response = self.client.post(
            '/api/business-requests/', self.payload, format='json'
        )

        self.assertEqual(response.status_code, 201)
        registration_request = BusinessRegistrationRequest.objects.get()
        self.assertEqual(registration_request.status, 'pending')
        self.assertEqual(
            registration_request.working_hours.count(),
            len(BusinessRegistrationHours.Weekday.choices),
        )
        self.assertEqual(response.data['business_name'], 'Smile Dental')
        self.assertEqual(response.data['status'], 'pending')

    def test_registration_accepts_photo_separate_from_json_data(self):
        image_buffer = BytesIO()
        Image.new('RGB', (1, 1), color='white').save(image_buffer, format='PNG')
        response = self.client.post(
            '/api/business-requests/',
            {
                'data': json.dumps(self.payload),
                'photo': SimpleUploadedFile(
                    'clinic.png', image_buffer.getvalue(), content_type='image/png'
                ),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 201, response.data)
        registration_request = BusinessRegistrationRequest.objects.get()
        self.assertTrue(
            registration_request.photo.name.startswith('business-registration/clinic')
        )
        self.assertTrue(registration_request.photo.name.endswith('.png'))
        self.assertEqual(registration_request.working_hours.count(), 7)

    def test_registration_requires_all_seven_weekdays(self):
        self.payload['working_hours'] = self.payload['working_hours'][:-1]

        response = self.client.post(
            '/api/business-requests/', self.payload, format='json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(BusinessRegistrationRequest.objects.exists())

    def test_registration_rejects_invalid_open_day_hours(self):
        self.payload['working_hours'][0]['closing_time'] = '08:00'

        response = self.client.post(
            '/api/business-requests/', self.payload, format='json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(BusinessRegistrationRequest.objects.exists())


class ReviewFlowTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = BusinessCategory.objects.create(
            name='Dental Clinic',
            slug='dental-clinic',
        )
        self.admin = User.objects.create_superuser(
            email='admin@appointflow.example',
            password='admin-pass-123',
            phone='+923000000000',
        )

    def _admin_client(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        return client

    def _submit_request(self):
        self.client.post(
            '/api/business-requests/', registration_payload(self.category.id), format='json'
        )
        return BusinessRegistrationRequest.objects.get()

    def test_admin_can_list_registration_requests(self):
        self._submit_request()

        response = self._admin_client().get('/api/admin/business-requests/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['business_name'], 'Smile Dental')

    def test_non_staff_cannot_list_registration_requests(self):
        self._submit_request()
        customer = User.objects.create_user(
            email='customer@example.com',
            password='customer-pass-123',
            phone='+923001111111',
        )
        non_staff_client = APIClient()
        non_staff_client.force_authenticate(user=customer)

        response = non_staff_client.get('/api/admin/business-requests/')

        self.assertEqual(response.status_code, 403)

    def test_approval_creates_business_with_hours_and_owner(self):
        registration_request = self._submit_request()

        response = self._admin_client().post(
            '/api/admin/business-requests/%d/approve/' % registration_request.id
        )

        self.assertEqual(response.status_code, 200)
        business = Business.objects.get()
        self.assertEqual(business.name, 'Smile Dental')
        self.assertEqual(business.owner.email, 'ali@example.com')
        self.assertEqual(business.working_hours.count(), 7)
        self.assertTrue(
            BusinessWorkingHours.objects.filter(
                business=business, weekday=6, is_closed=True
            ).exists()
        )
        registration_request.refresh_from_db()
        self.assertEqual(registration_request.status, 'approved')
        self.assertIsNotNone(registration_request.reviewed_at)
        self.assertIsNotNone(registration_request.reviewed_by)

    def test_approval_uses_existing_user_as_owner(self):
        existing_owner = User.objects.create_user(
            email='ali@example.com',
            password='existing-pass-123',
            phone='+923009876543',
        )
        registration_request = self._submit_request()

        self._admin_client().post(
            '/api/admin/business-requests/%d/approve/' % registration_request.id
        )

        business = Business.objects.get()
        self.assertEqual(business.owner, existing_owner)

    def test_second_approval_of_same_request_fails(self):
        registration_request = self._submit_request()
        approve_registration_request(registration_request, reviewed_by=self.admin)

        with self.assertRaises(ValidationError):
            approve_registration_request(registration_request, reviewed_by=self.admin)

    def test_reject_stores_reviewer_and_notes(self):
        registration_request = self._submit_request()

        response = self._admin_client().post(
            '/api/admin/business-requests/%d/reject/' % registration_request.id,
            {'admin_notes': 'Incomplete documents.'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        registration_request.refresh_from_db()
        self.assertEqual(registration_request.status, 'rejected')
        self.assertEqual(registration_request.admin_notes, 'Incomplete documents.')
        self.assertEqual(registration_request.reviewed_by, self.admin)
        self.assertFalse(Business.objects.exists())

    def test_reject_without_notes_is_accepted(self):
        registration_request = self._submit_request()

        response = self._admin_client().post(
            '/api/admin/business-requests/%d/reject/' % registration_request.id,
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        registration_request.refresh_from_db()
        self.assertEqual(registration_request.status, 'rejected')


class PublicBusinessAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = BusinessCategory.objects.create(
            name='Dental Clinic',
            slug='dental-clinic',
        )
        self.other_category = BusinessCategory.objects.create(
            name='Salon',
            slug='salon',
        )
        self.owner = User.objects.create_user(
            email='owner@example.com',
            password='owner-pass-123',
            first_name='Business',
            last_name='Owner',
            phone='+923001234567',
        )
        self.business = Business.objects.create(
            name='Smile Dental',
            slug='smile-dental',
            category=self.category,
            owner=self.owner,
            phone='+923001234567',
            email='hello@smile.example',
            city='Lahore',
            address='10 Main Road',
            description='Family dental clinic.',
        )
        BusinessWorkingHours.objects.create(
            business=self.business,
            weekday=0,
            is_closed=False,
            opening_time='09:00',
            closing_time='17:00',
        )

    def test_business_list_excludes_inactive_businesses(self):
        Business.objects.create(
            name='Inactive Dental',
            slug='inactive-dental',
            category=self.category,
            owner=self.owner,
            phone='+923001234567',
            city='Lahore',
            address='12 Main Road',
            description='Not publicly listed.',
            is_active=False,
        )

        response = self.client.get('/api/businesses/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['slug'] for item in response.data], ['smile-dental'])

    def test_business_list_filters_search_category_and_city(self):
        response = self.client.get(
            '/api/businesses/?search=family&category=dental-clinic&city=lahore'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['slug'] for item in response.data], ['smile-dental'])

        no_match_response = self.client.get('/api/businesses/?category=salon')
        self.assertEqual(no_match_response.status_code, 200)
        self.assertEqual(no_match_response.data, [])

    def test_business_detail_returns_category_and_working_hours(self):
        response = self.client.get('/api/businesses/smile-dental/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Smile Dental')
        self.assertEqual(response.data['category']['slug'], 'dental-clinic')
        self.assertEqual(response.data['working_hours'][0]['weekday_name'], 'Monday')
        self.assertEqual(response.data['working_hours'][0]['opening_time'], '09:00:00')

    def test_business_detail_hides_inactive_business(self):
        self.business.is_active = False
        self.business.save(update_fields=['is_active'])

        response = self.client.get('/api/businesses/smile-dental/')

        self.assertEqual(response.status_code, 404)
