from django.test import TestCase
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.test import APIClient
from rest_framework.test import APIRequestFactory

from .models import User


class AuthAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_signup_creates_user(self):
        payload = {
            'email': 'test@example.com',
            'password': 'strongpass123',
            'first_name': 'Test',
            'last_name': 'User',
            'phone': '1234567890',
        }

        response = self.client.post('/api/signup/', payload, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(email='test@example.com').exists())
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['phone'], '1234567890')

    def test_signup_requires_phone(self):
        payload = {
            'email': 'missing-phone@example.com',
            'password': 'strongpass123',
            'first_name': 'Test',
            'last_name': 'User',
        }

        missing_phone_response = self.client.post('/api/signup/', payload, format='json')
        payload['phone'] = ''
        blank_phone_response = self.client.post('/api/signup/', payload, format='json')

        self.assertEqual(missing_phone_response.status_code, 400)
        self.assertEqual(blank_phone_response.status_code, 400)

    def test_login_success(self):
        User.objects.create_user(
            email='login@example.com',
            password='strongpass123',
            first_name='Login',
            last_name='User',
        )

        response = self.client.post(
            '/api/login/',
            {'email': 'login@example.com', 'password': 'strongpass123'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user']['email'], 'login@example.com')
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

        request = APIRequestFactory().get(
            '/api/protected/',
            HTTP_AUTHORIZATION=f"Bearer {response.data['access']}",
        )
        authenticated_user, _ = JWTAuthentication().authenticate(request)
        self.assertEqual(authenticated_user, User.objects.get(email='login@example.com'))

        refresh_response = self.client.post(
            '/api/token/refresh/',
            {'refresh': response.data['refresh']},
            format='json',
        )
        self.assertEqual(refresh_response.status_code, 200)
        self.assertIn('access', refresh_response.data)

    def test_logout_blacklists_refresh_token(self):
        User.objects.create_user(
            email='logout@example.com',
            password='strongpass123',
            first_name='Log',
            last_name='Out',
        )
        login_response = self.client.post(
            '/api/login/',
            {'email': 'logout@example.com', 'password': 'strongpass123'},
            format='json',
        )
        refresh_token = login_response.data['refresh']

        logout_response = self.client.post(
            '/api/logout/', {'refresh': refresh_token}, format='json'
        )
        refresh_response = self.client.post(
            '/api/token/refresh/', {'refresh': refresh_token}, format='json'
        )

        self.assertEqual(logout_response.status_code, 200)
        self.assertEqual(refresh_response.status_code, 401)
