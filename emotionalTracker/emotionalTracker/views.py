from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from datetime import timedelta

from django.utils import timezone
from django.db.models import Q

from .models import Emotion, EmotionType, Collaborator
from .serializers import EmotionSerializer


class EmotionViewSet(viewsets.ModelViewSet):
    queryset = Emotion.objects.all()
    serializer_class = EmotionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Ensure users can only see their own emotions
        return Emotion.objects.filter(collaborator=self.request.user)

    @action(detail=False, methods=['GET'], url_path='emotion-types')
    def get_emotion_types(self, request):
        """

        Get all available emotion types
        """
        emotion_types = EmotionType.objects.all()
        serializer = EmotionSerializer(emotion_types, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['POST'], url_path='submit')
    def submit_emotion(self, request):
        """
        Submit emotion for the authenticated collaborator

        Constraints:
        - Only two submissions per day (morning and evening)
        - Morning submission before 12 PM
        - Evening submission after 12 PM and before end of day
        """

        # Get current time and collaborator
        now = timezone.now() + timedelta(hours=3)  # timezone in Madagascar
        collaborator = request.user
        today = now.date()

        # Validate emotion type
        emotion_type_id = request.data.get('emotion_type')
        try:
            emotion_type = EmotionType.objects.get(id=emotion_type_id)
        except EmotionType.DoesNotExist:
            return Response({
                'error': 'Invalid emotion type'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Determine half day and submission constraints
        current_hour = now.hour

        # Morning submission constraints (before 12 PM)
        if current_hour < 12:
            # Check if morning emotion already submitted
            morning_emotion = Emotion.objects.filter(
                collaborator=collaborator,
                date__date=today,
                half_day='morning'
            ).exists()

            if morning_emotion:
                return Response({
                    'error': 'Morning emotion already submitted'
                }, status=status.HTTP_400_BAD_REQUEST)

            half_day = 'morning'

        # Evening and post-12 PM logic
        else:
            # CRITICAL CHANGE: Prevent ANY morning submissions after 12 PM
            morning_emotion = Emotion.objects.filter(
                collaborator=collaborator,
                date__date=today,
                half_day='morning'
            ).first()

            # If no morning emotion and it's past 12 PM, morning submissions are NOT ALLOWED
            if not morning_emotion:
                return Response({
                    'error': "Morning emotion submission is no longer allowed after 12 PM"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check if evening emotion already submitted
            evening_emotion = Emotion.objects.filter(
                collaborator=collaborator,
                date__date=today,
                half_day='evening'
            ).exists()

            if evening_emotion:
                return Response({
                    'error': 'Evening emotion already submitted'
                }, status=status.HTTP_400_BAD_REQUEST)

            if current_hour >= 17:
                return Response({
                    'error': 'No more emotion submissions allowed after 5 PM'
                }, status=status.HTTP_400_BAD_REQUEST)

            half_day = 'evening'

        # Prepare emotion data
        emotion_data = {
            'emotion_type': emotion_type.id,
            'half_day': half_day
        }

        # Create and save emotion
        serializer = self.get_serializer(data=emotion_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['GET'], url_path='today')
    def get_today_emotions(self, request):
        """
         Get today's emotions for the authenticated collaborator
        """
        today = timezone.localdate()
        emotions = Emotion.objects.filter(
            collaborator=request.user,
            date__date=today
        ).order_by('half_day')

        # If no emotions or incomplete (only morning or only evening)
        if not emotions or emotions.count() < 2:
            # Check if morning is missing
            morning_emotion = emotions.filter(half_day='morning').first()
            evening_emotion = emotions.filter(half_day='evening').first()

            mada_timezone = timezone.now() + timedelta(hours=3)
            # If no morning emotion and past 12 PM, create placeholder
            if not morning_emotion and mada_timezone.hour >= 12:
                emotions = [evening_emotion] if evening_emotion else []

            # If no evening emotion and past 5 PM, create placeholder
            elif not evening_emotion and mada_timezone.hour >=17:
                emotions = [morning_emotion] if morning_emotion else []

            # If no submissions at all
            elif not emotions:
                emotions = []

        serializer = self.get_serializer(emotions, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        """
         Ensure the emotion is created with the correct collaborator
        """
        serializer.save(collaborator=self.request.user)


class EmotionOverviewSet(viewsets.ViewSet):
    """
    Provides an overview of emotions
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['GET'], url_path='overview')
    def emotion_overview(self, request):
        """
         Get emotion overview for the authenticated collaborator
        """
        collaborator = request.user

        return Response({
            'today_morning': EmotionSerializer(collaborator.emotion_today_morning).data if collaborator.emotion_today_morning else None,
            'today_evening': EmotionSerializer(collaborator.emotion_today_evening).data if collaborator.emotion_today_evening else None,
            'today': EmotionSerializer(collaborator.emotion_today, many=True).data,
            'week_degree': collaborator.emotion_degree_this_week,
            'week_emotion': collaborator.emotion_this_week,
            'month_degree': collaborator.emotion_degree_this_month,
            'month_emotion': collaborator.emotion_this_month
        })