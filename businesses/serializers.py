import json

from rest_framework import serializers

from .models import (
    Business,
    BusinessCategory,
    BusinessRegistrationHours,
    BusinessRegistrationRequest,
    BusinessWorkingHours,
)


class BusinessCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessCategory
        fields = ['id', 'name', 'slug', 'description']


class BusinessWorkingHoursSerializer(serializers.ModelSerializer):
    weekday_name = serializers.CharField(source='get_weekday_display', read_only=True)

    class Meta:
        model = BusinessWorkingHours
        fields = [
            'weekday',
            'weekday_name',
            'is_closed',
            'opening_time',
            'closing_time',
        ]


class PublicBusinessListSerializer(serializers.ModelSerializer):
    category = BusinessCategorySerializer(read_only=True)
    photo = serializers.SerializerMethodField()

    class Meta:
        model = Business
        fields = [
            'id',
            'name',
            'slug',
            'category',
            'city',
            'address',
            'description',
            'phone',
            'email',
            'photo',
        ]

    def get_photo(self, business):
        if not business.photo:
            return None
        request = self.context.get('request')
        photo_url = business.photo.url
        return request.build_absolute_uri(photo_url) if request else photo_url


class PublicBusinessDetailSerializer(PublicBusinessListSerializer):
    working_hours = BusinessWorkingHoursSerializer(many=True, read_only=True)

    class Meta(PublicBusinessListSerializer.Meta):
        fields = PublicBusinessListSerializer.Meta.fields + ['working_hours']


class BusinessRegistrationHoursInputSerializer(serializers.Serializer):
    weekday = serializers.ChoiceField(choices=BusinessRegistrationHours.Weekday.choices)
    is_closed = serializers.BooleanField()
    opening_time = serializers.TimeField(required=False, allow_null=True)
    closing_time = serializers.TimeField(required=False, allow_null=True)

    def validate(self, attrs):
        opening_time = attrs.get('opening_time')
        closing_time = attrs.get('closing_time')

        if attrs['is_closed']:
            if opening_time is not None or closing_time is not None:
                raise serializers.ValidationError(
                    'Closed days must not include opening or closing times.'
                )
        elif opening_time is None or closing_time is None:
            raise serializers.ValidationError(
                'Open days must include both opening and closing times.'
            )
        elif closing_time <= opening_time:
            raise serializers.ValidationError(
                'Closing time must be later than opening time.'
            )

        return attrs


class BusinessRegistrationRequestInputSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=BusinessCategory.objects.filter(is_active=True)
    )
    working_hours = BusinessRegistrationHoursInputSerializer(many=True)

    class Meta:
        model = BusinessRegistrationRequest
        fields = [
            'business_name',
            'category',
            'business_phone',
            'business_email',
            'city',
            'address',
            'description',
            'photo',
            'owner_full_name',
            'owner_email',
            'owner_phone',
            'working_hours',
        ]

    def to_internal_value(self, data):
        # Multipart form-data can carry one JSON text part plus a separate file.
        if hasattr(data, 'get') and isinstance(data.get('data'), str):
            multipart_data = data
            try:
                data = json.loads(multipart_data['data'])
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError(
                    {'data': 'Provide data as a valid JSON object.'}
                ) from exc
            if not isinstance(data, dict):
                raise serializers.ValidationError(
                    {'data': 'Provide data as a valid JSON object.'}
                )
            if multipart_data.get('photo') is not None:
                data['photo'] = multipart_data['photo']
        elif hasattr(data, 'get') and isinstance(data.get('working_hours'), str):
            data = data.copy()
            try:
                data['working_hours'] = json.loads(data['working_hours'])
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError(
                    {'working_hours': 'Provide working_hours as a valid JSON array.'}
                ) from exc
        return super().to_internal_value(data)

    def validate_working_hours(self, value):
        weekdays = [entry['weekday'] for entry in value]
        expected_weekdays = {choice.value for choice in BusinessRegistrationHours.Weekday}

        if len(weekdays) != len(expected_weekdays) or set(weekdays) != expected_weekdays:
            raise serializers.ValidationError(
                'Provide exactly one working-hours entry for each weekday (0=Monday through 6=Sunday).'
            )
        return value

    def create(self, validated_data):
        working_hours = validated_data.pop('working_hours')
        registration_request = BusinessRegistrationRequest.objects.create(**validated_data)
        BusinessRegistrationHours.objects.bulk_create(
            [
                BusinessRegistrationHours(
                    registration_request=registration_request,
                    **hours,
                )
                for hours in working_hours
            ]
        )
        return registration_request


class BusinessRegistrationRequestResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessRegistrationRequest
        fields = ['id', 'business_name', 'status', 'submitted_at']
        read_only_fields = fields


class BusinessRegistrationRequestAdminSerializer(serializers.ModelSerializer):
    category = BusinessCategorySerializer(read_only=True)
    working_hours = BusinessRegistrationHoursInputSerializer(many=True, read_only=True)

    class Meta:
        model = BusinessRegistrationRequest
        fields = [
            'id',
            'business_name',
            'category',
            'business_phone',
            'business_email',
            'city',
            'address',
            'description',
            'photo',
            'owner_full_name',
            'owner_email',
            'owner_phone',
            'working_hours',
            'status',
            'submitted_at',
            'reviewed_at',
            'reviewed_by',
            'admin_notes',
        ]
        read_only_fields = fields


class BusinessRegistrationRequestRejectSerializer(serializers.Serializer):
    admin_notes = serializers.CharField(required=False, allow_blank=True, default='')