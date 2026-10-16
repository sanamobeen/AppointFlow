from django.urls import path

from .views import (
    BusinessCategoryListView,
    BusinessRegistrationRequestAdminListView,
    BusinessRegistrationRequestApproveView,
    BusinessRegistrationRequestCreateView,
    BusinessRegistrationRequestRejectView,
    PublicBusinessDetailView,
    PublicBusinessListView,
)

urlpatterns = [
    path('business-categories/', BusinessCategoryListView.as_view(), name='business-category-list'),
    path('businesses/', PublicBusinessListView.as_view(), name='public-business-list'),
    path(
        'businesses/<slug:slug>/',
        PublicBusinessDetailView.as_view(),
        name='public-business-detail',
    ),
    path(
        'business-requests/',
        BusinessRegistrationRequestCreateView.as_view(),
        name='business-registration-request-create',
    ),
    path(
        'admin/business-requests/',
        BusinessRegistrationRequestAdminListView.as_view(),
        name='business-registration-request-admin-list',
    ),
    path(
        'admin/business-requests/<int:pk>/approve/',
        BusinessRegistrationRequestApproveView.as_view(),
        name='business-registration-request-approve',
    ),
    path(
        'admin/business-requests/<int:pk>/reject/',
        BusinessRegistrationRequestRejectView.as_view(),
        name='business-registration-request-reject',
    ),
]