from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.exceptions import ValidationError
from rest_framework_simplejwt.views import TokenObtainPairView
from datetime import timedelta

from django.contrib.auth import logout
from django.utils import timezone
from django.db.models import Q

from .models import Emotion, EmotionType, Collaborator
from .serializers import EmotionSerializer, CollaboratorCreateSerializer, CollaboratorDetailSerializer, EmotionTypeSerializer


class AuthViewSet(viewsets.ViewSet):
    """
    Authentication ViewSet for user registration, login, and logout
    """

    permission_classes = [AllowAny]

    @action(detail=False, methods=['POST'], url_path='register')
    def register(self, request):
        """
         Register a new collaborator
        """

        serializer = CollaboratorCreateSerializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save()

            # Generate tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'user': CollaboratorDetailSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'], url_path='login')
    def login(self, request):
        """
         Login a collaborator and return JWT tokens
        """
        email = request.data.get('email_address')
        password = request.data.get('password')

        if not email or not password:
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            user = Collaborator.objects.get(email_address=email)

            # Check password
            if not user.check_password(password):
                return Response({
                    'error': 'Invalid credentials'
                }, status=status.HTTP_401_UNAUTHORIZED)

            # Generate tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'user': CollaboratorDetailSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }, status=status.HTTP_200_OK)
        except Collaborator.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['POST'], url_path='logout')
    def logout(self, request):
        """
         Logout a collaborator by blacklisting the token
        """

        try:
            # Get the refresh token from the request
            refresh_token = request.data.get('refresh_token')

            if not refresh_token:
                return Response({
                    'error': 'Refresh token is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Blacklist the refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()

            # Django logout (optional, depending on your session management)
            logout(request)

            return Response({
                'message': 'Successfully logged out'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'error': 'Invalid token'
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['GET'], url_path='profile', permission_classes=[IsAuthenticated])
    def get_profile(self, request):
        """
         Get the current authenticated user's profile
        """
        user = request.user
        serializer = CollaboratorDetailSerializer(user)
        return Response(serializer.data)

    @action(detail=False, methods=['PUT', 'PATCH'], url_path='update-profile', permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        """
         Update the current authenticated user's profile
        """
        user = request.user
        serializer = CollaboratorCreateSerializer(
            user,
            data=request.data,
            partial=True # Allow partial updates
        )
        if serializer.is_valid():
            serializer.save()
            return Response(CollaboratorDetailSerializer(user).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
        serializer = EmotionTypeSerializer(emotion_types, many=True)
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

        if now.weekday() == 5 or now.weekday() == 6:
            return Response({
                'error': "C'est le week-end, vous ne pouvez déclarer vos émotions que durant la semaine de travail:"
            })

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
        else:

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
            'half_day': half_day,
            'collaborator': collaborator.id # avoid collaborator field submit error bc it requires this field
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
        today = timezone.localdate()
        week_number = today.isocalendar()[1]
        month = today.month
        year = today.year

        # Total number of submissions
        total_day = collaborator.emotions.filter(date__date=today).count()
        total_week = collaborator.emotions.filter(week_number=week_number, year=year).count()
        total_month = collaborator.emotions.filter(month=month, year=year).count()

        # General humor: positive if degree > 0, negative if < 0, neutral if = 0
        def general_humor(degree):
            if degree > 0:
                return "positive"
            elif degree < 0:
                return "negative"
            else:
                return "neutral"

        # Daily, weekly, monthly degrees
        degree_day = sum([e.emotion_degree for e in collaborator.emotions.filter(date__date=today)])
        degree_week = collaborator.emotion_degree_this_week
        degree_month = collaborator.emotion_degree_this_month

        # Participation percentage
        # Day: 2 max (morning + evening)
        percent_day = min(1.0, total_day / 2.0) * 100
        # Week: number of working days (Mon-Fri) in current week
        from calendar import weekday, monthrange
        week_days = [today + timedelta(days=i-today.weekday()) for i in range(5)]
        week_working_days = sum(1 for d in week_days if d.month == today.month)
        week_possible = week_working_days * 2
        percent_week = min(1.0, total_week / week_possible) * 100 if week_possible > 0 else 0

        # Month: number of working days (Mon-Fri) in current month
        _, last_day = monthrange(year, month)
        month_working_days = sum(1 for i in range(1, last_day+1) if weekday(year, month, i) < 5)
        month_possible = month_working_days * 2
        percent_month = min(1.0, total_month / month_possible) * 100 if month_possible > 0 else 0

        return Response({
            'today_morning': EmotionSerializer(collaborator.emotion_today_morning).data if collaborator.emotion_today_morning else None,
            'today_evening': EmotionSerializer(collaborator.emotion_today_evening).data if collaborator.emotion_today_evening else None,
            'today': EmotionSerializer(collaborator.emotion_today, many=True).data,
            'week_degree': collaborator.emotion_degree_this_week,
            'week_emotion': collaborator.emotion_this_week,
            'month_degree': collaborator.emotion_degree_this_month,
            'month_emotion': collaborator.emotion_this_month,

            # New fields
            'total_submissions_day': total_day,
            'total_submissions_week': total_week,
            'total_submissions_month': total_month,
            'general_humor_day': general_humor(degree_day),
            'general_humor_week': general_humor(degree_week),
            'general_humor_month': general_humor(degree_month),
            'participation_percentage_day': round(percent_day, 2),
            'participation_percentage_week': round(percent_week, 2),
            'participation_percentage_month': round(percent_month, 2)
        })