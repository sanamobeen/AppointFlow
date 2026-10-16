from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Business, BusinessCategory, BusinessRegistrationRequest
from .serializers import (
    BusinessCategorySerializer,
    BusinessRegistrationRequestAdminSerializer,
    BusinessRegistrationRequestInputSerializer,
    BusinessRegistrationRequestRejectSerializer,
    BusinessRegistrationRequestResponseSerializer,
    PublicBusinessDetailSerializer,
    PublicBusinessListSerializer,
)
from .services import (
    approve_registration_request,
    reject_registration_request,
)


class BusinessCategoryListView(generics.ListAPIView):
    serializer_class = BusinessCategorySerializer
    permission_classes = [AllowAny]
    queryset = BusinessCategory.objects.filter(is_active=True)


class BusinessRegistrationRequestCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = BusinessRegistrationRequestInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        registration_request = serializer.save()
        response_serializer = BusinessRegistrationRequestResponseSerializer(
            registration_request
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class PublicBusinessListView(generics.ListAPIView):
    serializer_class = PublicBusinessListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        businesses = Business.objects.filter(
            is_active=True,
            category__is_active=True,
        ).select_related('category')

        search = self.request.query_params.get('search', '').strip()
        category = self.request.query_params.get('category', '').strip()
        city = self.request.query_params.get('city', '').strip()

        if search:
            businesses = businesses.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(category__name__icontains=search)
            )
        if category:
            if category.isdigit():
                businesses = businesses.filter(category_id=int(category))
            else:
                businesses = businesses.filter(category__slug__iexact=category)
        if city:
            businesses = businesses.filter(city__icontains=city)

        return businesses


class PublicBusinessDetailView(generics.RetrieveAPIView):
    serializer_class = PublicBusinessDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    lookup_url_kwarg = 'slug'
    queryset = (
        Business.objects.filter(is_active=True, category__is_active=True)
        .select_related('category')
        .prefetch_related('working_hours')
    )


class BusinessRegistrationRequestAdminListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = BusinessRegistrationRequestAdminSerializer
    queryset = BusinessRegistrationRequest.objects.select_related(
        'category', 'reviewed_by'
    ).prefetch_related('working_hours')


class BusinessRegistrationRequestApproveView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        registration_request = get_object_or_404(
            BusinessRegistrationRequest, pk=pk
        )
        business = approve_registration_request(
            registration_request, reviewed_by=request.user
        )
        response_serializer = BusinessRegistrationRequestAdminSerializer(
            registration_request
        )
        return Response(
            {
                'message': 'Registration request approved.',
                'business_id': business.id,
                'business_slug': business.slug,
                'request': response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class BusinessRegistrationRequestRejectView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        registration_request = get_object_or_404(
            BusinessRegistrationRequest, pk=pk
        )
        notes_serializer = BusinessRegistrationRequestRejectSerializer(
            data=request.data
        )
        notes_serializer.is_valid(raise_exception=True)
        reject_registration_request(
            registration_request,
            reviewed_by=request.user,
            admin_notes=notes_serializer.validated_data['admin_notes'],
        )
        response_serializer = BusinessRegistrationRequestAdminSerializer(
            registration_request
        )
        return Response(
            {
                'message': 'Registration request rejected.',
                'request': response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )