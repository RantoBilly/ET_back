from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import (
    Cluster, Entity, Department, Service,
    Collaborator, EmotionType, Emotion
)


class ClusterSerializer(serializers.ModelSerializer):
    emotion_summary = serializers.SerializerMethodField()

    class Meta:
        model = Cluster
        fields = '__all__'
        read_only_fields = ['created_at']

    def get_emotion_summary(self, obj):
        return obj.emotion_summary


class EntitySerializer(serializers.ModelSerializer):
    cluster_name = serializers.CharField(source='cluster.name', read_only=True)
    emotion_summary = serializers.SerializerMethodField()

    class Meta:
        model = Entity
        fields = '__all__'
        read_only_fields = ['created_at']

    def get_emotion_summary(self, obj):
        return obj.emotion_summary


class DepartmentSerializer(serializers.ModelSerializer):
    entity_name = serializers.CharField(source='entity.name', read_only=True)
    emotion_summary = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = '__all__'
        read_only_fields = ['created_at']

    def get_emotion_summary(self, obj):
        return obj.emotion_summary


class ServiceSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    emotion_summary = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = '__all__'
        read_only_fields = ['created_at']

    def get_emotion_summary(self, obj):
        return obj.emotion_summary


class EmotionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmotionType
        fields = '__all__'
        read_only_fields = ['created_at', 'degree']


class CollaboratorCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    confirm_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Collaborator
        fields = [
            'id', 'email_address', 'first_name', 'last_name',
            'role', 'password', 'confirm_password',
            'cluster', 'entity', 'department', 'service',
            'manager', 'is_active', 'is_staff'
        ]
        extra_kwargs = {
            'email_address': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }

    def validate(self, attrs):
        # Vérifie seulement si l'utilisateur veut changer le mot de passe
        password = attrs.get('password')
        confirm_password = attrs.pop('confirm_password', None)

        if password and confirm_password:
            if password != confirm_password:
                raise serializers.ValidationError({"password": "Password fields didn't match."})
        elif password or confirm_password:
            # Un seul champ est fourni (incomplet)
            raise serializers.ValidationError({"password": "Both password and confirm_password are required to change password."})


        # Role-based hierarchy validation
        role = attrs.get('role')

        if role == 'pole_director':
            if attrs.get('entity') or attrs.get('department') or attrs.get('service'):
                raise serializers.ValidationError({
                    "role": "Pole Director should only have a cluster"
                })
            if not attrs.get('cluster'):
                raise serializers.ValidationError({
                    "cluster": "Pole Director must have a cluster"
                })

        elif role == 'entity_director':
            if attrs.get('department') or attrs.get('service'):
                raise serializers.ValidationError({
                    "role": "Entity Director should not have department and service anymore"
                })
            if not attrs.get('entity'):
                raise serializers.ValidationError({
                    "entity": "Entity Director must have an entity"
                })

        elif role == 'department_director':
            if attrs.get('service'):
                raise serializers.ValidationError({
                    "role": "Department Director should not have service anymore"
                })
            if not attrs.get('department'):
                raise serializers.ValidationError({
                    "department": "Department Director must have a department"
                })

        elif role == 'manager':
            if not attrs.get('service'):
                raise serializers.ValidationError({
                    "service": "Manager must have a service"
                })

        elif role == 'employee':
            if not attrs.get('service'):
                raise serializers.ValidationError({
                    "service": "Employee must have a service"
                })

        return attrs

    def create(self, validated_data):
        # Remove password confirmation before creating user
        validated_data.pop('confirm_password', None)

        # Create user with set_password to hash the password
        user = Collaborator.objects.create_user(
            email_address=validated_data.pop('email_address'),
            first_name=validated_data.pop('first_name'),
            last_name=validated_data.pop('last_name'),
            password=validated_data.pop('password'),
            **validated_data
        )

        try:
            user.full_clean()  # appèlle la méthode clean dans models.py
        except ValidationError as e:
            raise serializers.ValidationError(e.message_dict)

        user.save()
        return user

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        try:
            instance.full_clean()  # appelle explicite à clean()
        except ValidationError as e:
            raise serializers.ValidationError(e.message_dict)

        instance.save()
        return instance


class CollaboratorDetailSerializer(serializers.ModelSerializer):
    cluster_name = serializers.CharField(source='cluster.name', read_only=True)
    entity_name = serializers.CharField(source='entity.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    service_name = serializers.CharField(source='service.name', read_only=True)
    manager_name = serializers.SerializerMethodField()

    # Emotion-related fields
    emotion_today_morning = serializers.SerializerMethodField()
    emotion_today_evening = serializers.SerializerMethodField()
    emotion_today = serializers.SerializerMethodField()
    emotion_degree_this_week = serializers.SerializerMethodField()
    emotion_this_week = serializers.SerializerMethodField()
    emotion_degree_this_month = serializers.SerializerMethodField()
    emotion_this_month = serializers.SerializerMethodField()

    class Meta:
        model = Collaborator
        fields = [
            'id', 'email_address', 'first_name', 'last_name',
            'role', 'cluster_name', 'entity_name',
            'department_name', 'service_name',
            'manager_name', 'is_active', 'is_staff',
            # Emotion-related fields
            'emotion_today_morning', 'emotion_today_evening',
            'emotion_today', 'emotion_degree_this_week',
            'emotion_this_week', 'emotion_degree_this_month',
            'emotion_this_month'
        ]
        read_only_fields = fields

    def get_manager_name(self, obj):
        return f"{obj.manager.first_name} {obj.manager.last_name}" if obj.manager else None

    def get_emotion_today_morning(self, obj):
        emotion = obj.emotion_today_morning
        return EmotionSerializer(emotion).data if emotion else None

    def get_emotion_today_evening(self, obj):
        emotion = obj.emotion_today_evening
        return EmotionSerializer(emotion).data if emotion else None

    def get_emotion_today(self, obj):
        emotions = obj.emotion_today
        return EmotionSerializer(emotions, many=True).data if emotions else []

    def get_emotion_degree_this_week(self, obj):
        return obj.emotion_degree_this_week

    def get_emotion_this_week(self, obj):
        return obj.emotion_this_week

    def get_emotion_degree_this_month(self, obj):
        return obj.emotion_degree_this_month

    def get_emotion_this_month(self, obj):
        return obj.emotion_this_month


class EmotionSerializer(serializers.ModelSerializer):
    emotion_type_name = serializers.CharField(source='emotion_type.name', read_only=True)
    collaborator_name = serializers.SerializerMethodField()
    date_period = serializers.CharField(read_only=True)

    class Meta:
        model = Emotion
        fields = '__all__'
        read_only_fields = ['week_number', 'month', 'year', 'half_day', '_date_period']

    def get_collaborator_name(self, obj):
        return f"{obj.collaborator.first_name} {obj.collaborator.last_name}"

    def create(self, validated_data):
        # Ensure emotion_degree is set from emotion_type
        emotion_type = validated_data.get('emotion_type')
        validated_data['emotion_degree'] = emotion_type.degree if emotion_type else 0
        return super().create(validated_data)