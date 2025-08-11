from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.exceptions import ValidationError
from rest_framework_simplejwt.views import TokenObtainPairView
from datetime import timedelta
from calendar import weekday, monthrange

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

from django.contrib.auth import logout
from django.utils import timezone
from django.db.models import Q, Avg

from .models import Emotion, EmotionType, Collaborator, get_emotion_label_from_degree, Cluster
from .serializers import EmotionSerializer, CollaboratorCreateSerializer, CollaboratorDetailSerializer, EmotionTypeSerializer

today = timezone.localdate()
week_number = today.isocalendar()[1]
year = today.year
month = today.month


def get_emotion_label(degree):
    if degree <= -5:
        return "angry"
    elif degree <= -2:
        return "anxious"
    elif degree <= -1:
        return "sad"
    elif degree == 0:
        return "neutral"
    elif 0 < degree < 5:
        return "happy"
    elif degree >= 5:
        return "excited"
    return "neutral"


def general_humor(degree):
    if degree > 0:
        return "positive"
    elif degree < 0:
        return "negative"
    else:
        return "neutral"


# Helper to get emotion stats for a queryset of collaborators
def get_emotions_for_period(collaborators, period):
    emotions = Emotion.objects.filter(collaborator__in=collaborators)
    if period == 'day':
        emotions = emotions.filter(date__date=today)
    elif period == 'week':
        emotions = emotions.filter(week_number=week_number, year=year)
    elif period == 'month':
        emotions = emotions.filter(month=month, year=year)
    return emotions


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

        # Total number of submissions
        total_day = collaborator.emotions.filter(date__date=today).count()
        total_week = collaborator.emotions.filter(week_number=week_number, year=year).count()
        total_month = collaborator.emotions.filter(month=month, year=year).count()

        # Daily, weekly, monthly degrees
        degree_day = sum([e.emotion_degree for e in collaborator.emotions.filter(date__date=today)])
        degree_week = collaborator.emotion_degree_this_week
        degree_month = collaborator.emotion_degree_this_month

        # Participation percentage
        # Day: 2 max (morning + evening)
        percent_day = min(1.0, total_day / 2.0) * 100
        # Week: number of working days (Mon-Fri) in current week
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


class ManagerOverViewSet(viewsets.ViewSet):
    """
    Provides an overview for a manager about their subordinates
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['GET'], url_path='manager-overview')
    def manager_overview(self, request):
        manager = request.user

        # Ensure the user is a manager
        if manager.role != 'manager':
            return Response({'error': 'You are not a manager'}, status=status.HTTP_403_FORBIDDEN)

        # subordinates
        subordinates = manager.subordinates.all()
        subordinate_names = [f"{c.first_name} {c.last_name}" for c in subordinates]
        total_subordinates = subordinates.count()

        # count submission
        total_submissions_day = get_emotions_for_period(subordinates, 'day').count()
        total_submissions_week = get_emotions_for_period(subordinates, 'week').count()
        total_submissions_month = get_emotions_for_period(subordinates, 'month').count()

        # Participation percentage
        # Day: 2 max per subordinates
        percent_day = min(1.0, total_submissions_day / (total_subordinates * 2) if total_subordinates > 0 else 0) * 100
        # week : working days in week
        week_days = [today + timedelta(days=i-today.weekday()) for i in range(5)]
        week_working_days = sum(1 for d in week_days if d.month == today.month)
        week_possible = total_subordinates * week_working_days * 2
        total_unsubmit_week = week_possible - total_submissions_week # collaborateurs n'ayant pas submit
        percent_week = min(1.0, total_submissions_week / week_possible if week_possible > 0 else 0) * 100

        # Month: working days in month
        _, last_day = monthrange(year, month)
        month_working_days = sum(1 for i in range(1, last_day+1) if weekday(year, month, i) < 5)
        month_possible = total_subordinates * month_working_days * 2
        total_unsubmit_month = month_possible - total_submissions_month
        percent_month = min(1.0, total_submissions_month / month_possible if month_possible > 0 else 0) * 100

        # Emotion degree for all subordinates
        degree_day = sum([e.emotion_degree for e in get_emotions_for_period(subordinates, 'day')])
        degree_week = sum([e.emotion_degree for e in get_emotions_for_period(subordinates, 'week')])
        degree_month = sum([e.emotion_degree for e in get_emotions_for_period(subordinates, 'month')])

        emotion_today = get_emotion_label(degree_day)
        emotion_this_week = get_emotion_label(degree_week)
        emotion_this_month = get_emotion_label(degree_month)

        # general humor
        general_humor_day = general_humor(degree_day)
        general_humor_week = general_humor(degree_week)
        general_humor_month = general_humor(degree_month)

        # Subordinates to supervise (those with negative emotion_degree today, week or month)
        subordinates_to_supervise = []
        for subordinate in subordinates:
            if (
                subordinate.emotion_degree_this_week < 0
                or subordinate.emotion_degree_this_month < 0
                or sum([e.emotion_degree for e in subordinate.emotions.filter(date__date=today)]) < 0
            ):
                subordinates_to_supervise.append(f"{subordinate.first_name} {subordinate.last_name}")

        # Service name
        service_name = manager.service.name if manager.service else None

        return Response({
            'service_name ': service_name,
            'subordinate_names': subordinate_names,
            'total_subordinates': total_subordinates,
            'total_submissions_day': total_submissions_day,
            'total_submissions_week': total_submissions_week,
            'total_submissions_month': total_submissions_month,
            'participation_percentage_day': round(percent_day, 2),
            'participation_percentage_week': round(percent_week, 2),
            'participation_percentage_month': round(percent_month, 2),
            'emotion_degree_day': degree_day,
            'emotion_degree_week': degree_week,
            'emotion_degree_month': degree_month,
            'emotion_today': emotion_today,
            'emotion_this_week': emotion_this_week,
            'emotion_this_month': emotion_this_month,
            'general_humor_day': general_humor_day,
            'general_humor_week': general_humor_week,
            'general_humor_month': general_humor_month,
            'subordinates_to_supervise': subordinates_to_supervise,
        })


class DepartmentDirectorOverviewSet(viewsets.ViewSet):
    """
    Provides an overview for a department director about their department and its services
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['GET'], url_path='department-director-overview')
    def department_director_overview(self, request):
        director = request.user

        # Ensure the user is a department director
        if director.role != 'department_director':
            return Response({'error': 'You are not a department director'}, status=status.HTTP_403_FORBIDDEN)

        department = director.department
        if not department:
            return Response({'error': 'No department assigned'}, status=status.HTTP_400_BAD_REQUEST)


        services = department.services.all()
        num_services = services.count()
        service_names = [service.name for service in services]

        # Aggrecated metrics
        total_collaborators = 0
        total_participation_week_possible = 0
        total_participation_month_possible = 0
        total_submissions_day = 0
        total_submissions_week = 0
        total_submissions_month = 0
        total_participation_day = 0
        total_participation_week = 0
        total_participation_month = 0
        total_general_humor_day = 0
        total_general_humor_week = 0
        total_general_humor_month = 0

        total_emotion_degree_day_department = 0
        total_emotion_degree_week_department = 0
        total_emotion_degree_month_department = 0

        service_to_supervise = []

        services_data = []

        for service in services:
            collaborators = service.collaborators.all()

            collaborators_to_supervise = []
            for collaborator in service.collaborators.all():
                if (
                    collaborator.emotion_degree_this_week < 0
                    or collaborator.emotion_degree_this_month < 0
                    or sum(e.emotion_degree for e in collaborator.emotions.filter(date__date=today)) < 0
                ):
                    collaborators_to_supervise.append(f"{collaborator.first_name} {collaborator.last_name}")

            manager = collaborators.filter(role='manager').first()

            employees = collaborators.filter(role='employee')
            total_collaborators += collaborators.count()

            # Submissions
            submissions_day = get_emotions_for_period(collaborators, 'day').count()
            submissions_week = get_emotions_for_period(collaborators, 'week').count()
            submissions_month = get_emotions_for_period(collaborators, 'month').count()

            # Participation percentages
            # Day: 2 per collaborator
            percent_day = min(1.0, submissions_day / (collaborators.count() * 2) if collaborators.count() else 0) * 100
            # Week: working days
            week_days = [today + timedelta(days=i - today.weekday()) for i in range(5)]
            week_working_days = sum(1 for d in week_days if d.month == today.month)
            week_possible = collaborators.count() * week_working_days * 2
            total_unsubmit_week = week_possible - submissions_week  # collaborateurs n'ayant pas submit
            percent_week = min(1.0, submissions_week / week_possible if week_possible > 0 else 0) * 100
            # Month: working days
            _, last_day = monthrange(year, month)
            month_working_days = sum(1 for i in range(1, last_day + 1) if weekday(year, month, i) < 5)
            month_possible = collaborators.count() * month_working_days * 2
            total_unsubmit_month = month_possible - submissions_month
            percent_month = min(1.0, submissions_month / month_possible if month_possible > 0 else 0) * 100

            # Total of participation in the department
            total_participation_week_possible += week_possible
            total_participation_month_possible += month_possible

            # Emotion degree
            degree_day = sum([e.emotion_degree for e in get_emotions_for_period(collaborators, 'day')])
            degree_week = sum([e.emotion_degree for e in get_emotions_for_period(collaborators, 'week')])
            degree_month = sum([e.emotion_degree for e in get_emotions_for_period(collaborators, 'month')])

            emotion_day_service = get_emotion_label(degree_day)
            emotion_week_service = get_emotion_label(degree_week)
            emotion_month_service = get_emotion_label(degree_month)

            humor_day = general_humor(degree_day)
            humor_week = general_humor(degree_week)
            humor_month = general_humor(degree_month)

            # Aggregate total metrics
            total_submissions_day += submissions_day
            total_submissions_week += submissions_week
            total_submissions_month += submissions_month
            total_participation_day += percent_day
            total_participation_week += percent_week
            total_participation_month += percent_month

            # getting emotion (D, W, M) for the departments
            total_emotion_degree_day_department += degree_day
            total_emotion_degree_week_department += degree_week
            total_emotion_degree_month_department += degree_month

            # For general_humor, count negative (for service_to_supervise)
            if humor_day == "negative" or humor_week == "negative" or humor_month == "negative":
                service_to_supervise.append(service.name)

                # Service metrics
            services_data.append({
                'service_name': service.name,
                'manager_name': f"{manager.first_name} {manager.last_name}" if manager else None,
                'employees_names': [f"{emp.first_name} {emp.last_name}" for emp in employees],
                'total_collaborators': collaborators.count(),
                'total_submissions_week_possible': week_possible,
                'total_submissions_month_possible': month_possible,
                'total_submissions_day': submissions_day,
                'total_submissions_week': submissions_week,
                'total_submissions_month': submissions_month,
                'unsubmitted_week_collaborators': total_unsubmit_week,
                'unsubmitted_month_collaborators': total_unsubmit_month,
                'percent_submission_week': round(submissions_week / week_possible if week_possible else 0, 2),
                'percent_submission_month': round(submissions_month / month_possible if month_possible else 0, 2),
                'participation_percentage_day': round(percent_day, 2),
                'participation_percentage_week': round(percent_week, 2),
                'participation_percentage_month': round(percent_month, 2),
                'emotion_day_service': emotion_day_service,
                'emotion_week_service': emotion_week_service,
                'emotion_month_service': emotion_month_service,
                'general_humor_day': humor_day,
                'general_humor_week': humor_week,
                'general_humor_month': humor_month,
                'collaborators_to_supervise': collaborators_to_supervise,
            })

        # For total general humor: sum up humor scores, or aggregate as needed (here, simply count negatives/positives)
        # For simplicity, below shows the average participation and majority general humor
        def aggregate_general_humor(services_data, period):
            humors = [service[f'general_humor_{period}'] for service in services_data]
            count_positive = humors.count("positive")
            count_negative = humors.count("negative")
            return "positive" if count_positive > count_negative else (
                "negative" if count_negative > count_positive else "neutral")

        return Response({
            'department_name': department.name,
            'num_services': num_services,
            'service_names': service_names,
            'services': services_data,
            'total_collaborators': total_collaborators,
            'total_participation_week_possible': total_participation_week_possible,
            'total_participation_month_possible': total_participation_month_possible,
            'total_submissions_day': total_submissions_day,
            'total_submissions_week': total_submissions_week,
            'unsubmitted_collaborators_week': total_participation_week_possible - total_submissions_week,
            'unsubmitted_collaborators_month': total_participation_month_possible - total_submissions_month,
            'total_submissions_month': total_submissions_month,
            'percent_submission_week': round(total_submissions_week / total_participation_week_possible if total_participation_week_possible else 0, 2),
            'percent_submission_month': round(total_submissions_month / total_participation_month_possible if total_participation_month_possible else 0, 2),
            'participation_percentage_day': round(total_participation_day / num_services if num_services else 0, 2),
            'participation_percentage_week': round(total_participation_week / num_services if num_services else 0, 2),
            'participation_percentage_month': round(total_participation_month / num_services if num_services else 0, 2),
            'general_humor_day': aggregate_general_humor(services_data, 'day'),
            'general_humor_week': aggregate_general_humor(services_data, 'week'),
            'general_humor_month': aggregate_general_humor(services_data, 'month'),

            'emotion_today': get_emotion_label(total_emotion_degree_day_department),
            'emotion_week': get_emotion_label(total_emotion_degree_week_department),
            'emotion_month': get_emotion_label(total_emotion_degree_month_department),

            'service_to_supervise': service_to_supervise,
        })

    @action(detail=False, methods=['GET'], url_path='department-director-reporting-pdf')
    def department_director_reporting_pdf(self, request):
        director = request.user

        # Get the data as you do in department_director_overview
        if director.role != 'department_director':
            return Response({'error': 'You are not a department director'}, status=status.HTTP_403_FORBIDDEN)

        department = director.department
        if not department:
            return Response({'error': 'No department assigned'}, status=status.HTTP_400_BAD_REQUEST)

        overview = self.department_director_overview(request).data

        # Create PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="department_report.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)

        styles = getSampleStyleSheet()
        elements = []

        # Custom styles
        title_style = ParagraphStyle(name='Title', fontSize=18, textColor=colors.HexColor("#002b49"), spaceAfter=12)
        header_style = ParagraphStyle(name='Header', fontSize=14, textColor=colors.black, spaceBefore=12, spaceAfter=6)
        normal_style = ParagraphStyle(name='Normal', fontSize=10, textColor=colors.black)
        bold_style = ParagraphStyle(name='Bold', fontSize=10, textColor=colors.black, spaceAfter=6, leading=14)

        # Title
        elements.append(Paragraph(f"Reporting – Département : {overview['department_name']}", title_style))
        elements.append(Spacer(1, 12))

        # General Stats Table
        general_data = [
            ['Nombre de services', overview['num_services']],
            ['Total collaborateurs globale', overview['total_collaborators']],
            ['Total de soumissions possible globale', f"{overview['total_participation_month_possible']}"],
            ['Soumissions achevés globale',
             f"{overview['total_submissions_month']}"],
            ['Sousmissions inachevés globale', f"{overview['unsubmitted_collaborators_month']}"],
            ['Taux de participation (%)',
             f"{overview['percent_submission_month']}"],
            ['Tendance Emotionnelle globale', f"{overview['emotion_month']}"]
        ]
        table = Table(general_data, colWidths=[7 * cm, 8 * cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#002b49")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f2f2f2")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 18))

        # Service details
        elements.append(Paragraph("Détails des services :", header_style))
        for service in overview['services']:
            data = [
                ['Nom du service', service['service_name']],
                ['Manager', service['manager_name'] or 'Non assigné'],
                ['Collaborateurs', ', '.join(service['employees_names'])],
                ['Total collaborateurs', service['total_collaborators']],
                ['Total de soumissions possible', service['total_submissions_month_possible']],
                ['Soumissions achevés',
                 f"{service['total_submissions_month']}"],
                ['Soumissions inachevés', service['unsubmitted_month_collaborators']],
                ['Participation % (J/S/M)',
                 f"{service['percent_submission_month']}"],
                ['Tendance Emotionnelle', service['emotion_month_service']],
                ['À superviser', ', '.join(service['collaborators_to_supervise']) or '—']
            ]
            service_table = Table(data, colWidths=[6.5 * cm, 8.5 * cm])
            service_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#dce3ea")),
                ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ]))
            elements.append(service_table)
            elements.append(Spacer(1, 12))

        # Services à superviser
        elements.append(Paragraph("Services à superviser :", header_style))
        service_list = ', '.join(overview['service_to_supervise']) or 'Aucun'
        elements.append(Paragraph(service_list, normal_style))

        doc.build(elements)
        return response


class EntityDirectorOverviewSet(viewsets.ViewSet):
    """
    Provides an overview for an entity director about their entity and its departments
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['GET'], url_path='entity-director-overview')
    def entity_director_overview(self, request):
        director = request.user

        # Ensure the user is an entity director
        if director.role != 'entity_director':
            return Response({'error': 'You are not an entity director'}, status=status.HTTP_403_FORBIDDEN)

        entity = director.entity
        if not entity:
            return Response({'error': 'No entity assigned'}, status=status.HTTP_400_BAD_REQUEST)

        departments = entity.departments.all()
        num_departments = departments.count()
        department_names = [dept.name for dept in departments]
        num_departments = departments.count()

        # Aggregated metrics
        total_collaborators = 0
        total_submissions_day = 0
        total_submissions_week = 0
        total_submissions_month = 0
        total_participation_day = 0
        total_participation_week = 0
        total_participation_month = 0
        total_participation_week_possible = 0
        total_participation_month_possible = 0
        department_to_supervise = []  # Departments where any service_to_supervise exists

        total_emotion_degree_day_entity = 0
        total_emotion_degree_week_entity = 0
        total_emotion_degree_month_entity = 0

        departments_data = []

        for department in departments:
            services = department.services.all()
            collaborators = []
            service_names = [service.name for service in services]
            service_to_supervise = []  # Services in this department needing supervision

            # Find department director
            dept_director = department.collaborators.filter(role='department_director').first()
            dept_director_name = f"{dept_director.first_name} {dept_director.last_name}" if dept_director else None

            department_total_collaborators = 0
            department_submissions_day = 0
            department_submissions_week = 0
            department_submissions_month = 0
            department_participation_day = 0
            department_participation_week = 0
            department_participation_month = 0
            total_participation_week_possible_department = 0
            total_participation_month_possible_department = 0

            total_emotion_degree_day_department = 0
            total_emotion_degree_week_department = 0
            total_emotion_degree_month_department = 0

            services_data = []

            for service in services:
                service_collaborators = list(service.collaborators.all())
                collaborators += service_collaborators
                department_total_collaborators += len(service_collaborators)

                collaborators_to_supervise = []
                for collaborator in service.collaborators.all():
                    if (
                            collaborator.emotion_degree_this_week < 0
                            or collaborator.emotion_degree_this_month < 0
                            or sum(e.emotion_degree for e in collaborator.emotions.filter(date__date=today)) < 0
                    ):
                        collaborators_to_supervise.append(f"{collaborator.first_name} {collaborator.last_name}")

                # Submissions
                submissions_day = get_emotions_for_period(service_collaborators, 'day').count()
                submissions_week = get_emotions_for_period(service_collaborators, 'week').count()
                submissions_month = get_emotions_for_period(service_collaborators, 'month').count()

                # Participation percentages
                percent_day = min(1.0, submissions_day / (len(service_collaborators) * 2) if len(
                    service_collaborators) else 0) * 100
                week_days = [today + timedelta(days=i - today.weekday()) for i in range(5)]
                week_working_days = sum(1 for d in week_days if d.month == today.month)
                week_possible = len(service_collaborators) * week_working_days * 2
                percent_week = min(1.0, submissions_week / week_possible if week_possible > 0 else 0) * 100
                _, last_day = monthrange(year, month)
                month_working_days = sum(1 for i in range(1, last_day + 1) if weekday(year, month, i) < 5)
                month_possible = len(service_collaborators) * month_working_days * 2
                percent_month = min(1.0, submissions_month / month_possible if month_possible > 0 else 0) * 100

                total_participation_week_possible_department += week_possible
                total_participation_month_possible_department += month_possible

                # Emotion degree
                degree_day = sum([e.emotion_degree for e in get_emotions_for_period(service_collaborators, 'day')])
                degree_week = sum([e.emotion_degree for e in get_emotions_for_period(service_collaborators, 'week')])
                degree_month = sum([e.emotion_degree for e in get_emotions_for_period(service_collaborators, 'month')])

                total_emotion_degree_day_department += degree_day
                total_emotion_degree_week_department += degree_week
                total_emotion_degree_month_department += degree_month

                humor_day = general_humor(degree_day)
                humor_week = general_humor(degree_week)
                humor_month = general_humor(degree_month)

                # Aggregate totals for department
                department_submissions_day += submissions_day
                department_submissions_week += submissions_week
                department_submissions_month += submissions_month
                department_participation_day += percent_day
                department_participation_week += percent_week
                department_participation_month += percent_month

                # For service_to_supervise
                if humor_day == "negative" or humor_week == "negative" or humor_month == "negative":
                    service_to_supervise.append(service.name)

                manager = service.collaborators.filter(role='manager').first()
                employees = service.collaborators.filter(role='employee')

                services_data.append({
                    'service_name': service.name,
                    'manager_name': f"{manager.first_name} {manager.last_name}" if manager else None,
                    'employees_names': [f"{emp.first_name} {emp.last_name}" for emp in employees],
                    'total_collaborators': len(service_collaborators),
                    'total_submissions_day': submissions_day,
                    'total_submissions_week': submissions_week,
                    'total_submissions_month': submissions_month,
                    'participation_percentage_day': round(percent_day, 2),
                    'participation_percentage_week': round(percent_week, 2),
                    'participation_percentage_month': round(percent_month, 2),
                    'general_humor_day': humor_day,
                    'general_humor_week': humor_week,
                    'general_humor_month': humor_month,
                    'collaborators_to_supervise': collaborators_to_supervise,
                })

            # For total general humor: aggregate by majority
            def aggregate_general_humor(services_data, period):
                humors = [service[f'general_humor_{period}'] for service in services_data]
                count_positive = humors.count("positive")
                count_negative = humors.count("negative")
                return "positive" if count_positive > count_negative else (
                    "negative" if count_negative > count_positive else "neutral")

            departments_data.append({
                'department_name': department.name,
                'department_director_name': dept_director_name,
                'service_names': service_names,
                'services': services_data,
                'total_collaborators': department_total_collaborators,
                'total_participation_week_possible_department': total_participation_week_possible_department,
                'total_participation_month_possible_department': total_participation_month_possible_department,
                'total_submissions_day': department_submissions_day,
                'total_submissions_week': department_submissions_week,
                'total_submissions_month': department_submissions_month,
                'unsubmitted_collaborators_week_department': total_participation_week_possible_department - department_submissions_week,
                'unsubmitted_collaborators_month_department': total_participation_month_possible_department - department_submissions_month,
                'percent_submission_week_department': round(department_submissions_week / total_participation_week_possible_department if total_participation_week_possible_department else 0, 2),
                'percent_submission_month_department': round(department_submissions_month / total_participation_month_possible_department if total_participation_month_possible_department else 0, 2),
                'participation_percentage_day': round(
                    department_participation_day / len(services) if len(services) else 0, 2),
                'participation_percentage_week': round(
                    department_participation_week / len(services) if len(services) else 0, 2),
                'participation_percentage_month': round(
                    department_participation_month / len(services) if len(services) else 0, 2),
                'general_humor_day': aggregate_general_humor(services_data, 'day'),
                'general_humor_week': aggregate_general_humor(services_data, 'week'),
                'general_humor_month': aggregate_general_humor(services_data, 'month'),

                'emotion_today_department': get_emotion_label(total_emotion_degree_day_department),
                'emotion_week_department': get_emotion_label(total_emotion_degree_week_department),
                'emotion_month_department': get_emotion_label(total_emotion_degree_month_department),

                'service_to_supervise': service_to_supervise,
            })

            total_collaborators += department_total_collaborators
            total_submissions_day += department_submissions_day
            total_submissions_week += department_submissions_week
            total_submissions_month += department_submissions_month
            total_participation_week_possible += total_participation_week_possible_department
            total_participation_month_possible += total_participation_month_possible_department
            total_participation_day += department_participation_day / len(services) if len(services) else 0
            total_participation_week += department_participation_week / len(services) if len(services) else 0
            total_participation_month += department_participation_month / len(services) if len(services) else 0

            total_emotion_degree_day_entity += total_emotion_degree_day_department
            total_emotion_degree_week_entity += total_emotion_degree_week_department
            total_emotion_degree_month_entity += total_emotion_degree_month_department

            if service_to_supervise:
                department_to_supervise.append(department.name)

                # For total general humor: aggregate by majority
        def aggregate_general_humor(departments_data, period):
            humors = [dept[f'general_humor_{period}'] for dept in departments_data]
            count_positive = humors.count("positive")
            count_negative = humors.count("negative")
            return "positive" if count_positive > count_negative else (
                "negative" if count_negative > count_positive else "neutral")

        return Response({
            'entity_name': entity.name,
            'department_names': department_names,
            'num_departments': num_departments,
            'departments': departments_data,
            'total_collaborators': total_collaborators,
            'total_participation_week_possible': total_participation_week_possible,
            'total_participation_month_possible': total_participation_month_possible,
            'total_submissions_day': total_submissions_day,
            'total_submissions_week': total_submissions_week,
            'total_submissions_month': total_submissions_month,
            'unsubmitted_collaborators_week': total_participation_week_possible - total_submissions_week,
            'unsubmitted_collaborators_month': total_participation_month_possible - total_submissions_month,
            'percent_submission_week': round(total_submissions_week / total_participation_week_possible if total_participation_week_possible else 0, 2),
            'percent_submission_month': round(total_submissions_month / total_participation_month_possible if total_participation_month_possible else 0, 2),
            'participation_percentage_day': round(total_participation_day / num_departments if num_departments else 0,
                                                  2),
            'participation_percentage_week': round(total_participation_week / num_departments if num_departments else 0,
                                                   2),
            'participation_percentage_month': round(
                total_participation_month / num_departments if num_departments else 0, 2),
            'general_humor_day': aggregate_general_humor(departments_data, 'day'),
            'general_humor_week': aggregate_general_humor(departments_data, 'week'),
            'general_humor_month': aggregate_general_humor(departments_data, 'month'),

            'emotion_today': get_emotion_label(total_emotion_degree_day_entity),
            'emotion_week': get_emotion_label(total_emotion_degree_week_entity),
            'emotion_month': get_emotion_label(total_emotion_degree_month_entity),

            'department_to_supervise': department_to_supervise,
        })

    @action(detail=False, methods=['GET'], url_path='entity-director-reporting-pdf')
    def entity_director_reporting_pdf(self, request):
        director = request.user

        # Get the data as you do in entity_director_overview
        if director.role != 'entity_director':
            return Response({'error': 'You are not an entity director'}, status=status.HTTP_403_FORBIDDEN)

        entity = director.entity
        if not entity:
            return Response({'error': 'No entity assigned'}, status=status.HTTP_400_BAD_REQUEST)

        overview = self.entity_director_overview(request).data

        # Create PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="entity_report.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)

        styles = getSampleStyleSheet()
        elements = []

        # Custom styles
        title_style = ParagraphStyle(name='Title', fontSize=18, textColor=colors.HexColor("#002b49"), spaceAfter=12)
        header_style = ParagraphStyle(name='Header', fontSize=14, textColor=colors.black, spaceBefore=12, spaceAfter=6)
        normal_style = ParagraphStyle(name='Normal', fontSize=10, textColor=colors.black)
        bold_style = ParagraphStyle(name='Bold', fontSize=10, textColor=colors.black, spaceAfter=6, leading=14)

        # Title
        elements.append(Paragraph(f"Reporting – Entité : {overview['entity_name']}", title_style))
        elements.append(Spacer(1, 12))

        # General Stats Table
        general_data = [
            ['Nombre de départements', overview['num_departments']],
            ['Total collaborateurs', overview['total_collaborators']],
            ['Nombre de soumissions globale', overview['total_participation_month_possible']],
            ['Nombre de soumissions achevés globale',
             f"{overview['total_submissions_month']}"],
            ['Nombre de soumissions inachevés globale', overview['unsubmitted_collaborators_month']],
            ['Taux de participation globale (%)',
             f"{overview['percent_submission_month']}"],
            ['Tendance emotionnele globale', overview['emotion_month']],
        ]
        table = Table(general_data, colWidths=[7 * cm, 8 * cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#002b49")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f2f2f2")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 18))

        # Department details
        elements.append(Paragraph("Détails des départements :", header_style))
        for department in overview['departments']:
            data = [
                ['Nom du département', department['department_name']],
                ['Directeur', department['department_director_name'] or 'Non assigné'],
                ['Services', ', '.join(department['service_names'])],
                ['Total collaborateurs', department['total_collaborators']],
                ['Total de soumissions', department['total_participation_month_possible_department']],
                ['Soumissions achevés',
                 f"{department['total_submissions_month']}"],
                ['Soumissions inachevés', department['unsubmitted_collaborators_month_department']],
                ['Taux de Participation % (J/S/M)',
                 f"{department['percent_submission_month_department']}"],
                ['Tendance emotionnelle', department['emotion_month_department']],
                ['À superviser', ', '.join(department['service_to_supervise']) or '—']
            ]
            department_table = Table(data) # , colWidths=[6.5 * cm, 8.5 * cm]
            department_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#dce3ea")),
                ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ]))
            elements.append(department_table)
            elements.append(Spacer(1, 12))

        # Footer: departments to supervise
        elements.append(Paragraph("Départements à superviser :", header_style))
        department_list = ', '.join(overview['department_to_supervise']) or 'Aucun'
        elements.append(Paragraph(department_list, normal_style))

        doc.build(elements)
        return response


class PoleDirectorOverviewSet(viewsets.ViewSet):
    """
    Provides an overview for a pole director about their cluster and its entities
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['GET'], url_path='pole-director-overview')
    def pole_director_overview(self, request):
        director = request.user

        # Ensure the user is a pole director
        if director.role != 'pole_director':
            return Response({'error': 'You are not a pole director'}, status=status.HTTP_403_FORBIDDEN)

        cluster = director.cluster
        if not cluster:
            return Response({'error': 'No cluster assigned'}, status=status.HTTP_400_BAD_REQUEST)

        entities = cluster.entities.all()
        num_entities = entities.count()
        entity_names = [entity.name for entity in entities]

        # Aggregated metrics
        total_collaborators = 0

        total_participation_week_possible = 0
        total_participation_month_possible = 0

        total_submissions_day = 0
        total_submissions_week = 0
        total_submissions_month = 0
        total_participation_day = 0
        total_participation_week = 0
        total_participation_month = 0

        total_emotion_degree_day_cluster = 0
        total_emotion_degree_week_cluster = 0
        total_emotion_degree_month_cluster = 0

        entity_to_supervise = []  # Entities where any department_to_supervise exists

        entities_data = []

        for entity in entities:
            departments = entity.departments.all()
            collaborators = []
            department_names = [dept.name for dept in departments]
            department_to_supervise = []  # Departments in this entity needing supervision

            # Find entity director
            entity_director = entity.collaborators.filter(role='entity_director').first()
            entity_director_name = f"{entity_director.first_name} {entity_director.last_name}" if entity_director else None

            entity_total_collaborators = 0

            total_participation_week_possible_entity = 0
            total_participation_month_possible_entity = 0

            entity_submissions_day = 0
            entity_submissions_week = 0
            entity_submissions_month = 0
            entity_participation_day = 0
            entity_participation_week = 0
            entity_participation_month = 0

            total_emotion_degree_day_entity = 0
            total_emotion_degree_week_entity = 0
            total_emotion_degree_month_entity = 0

            departments_data = []

            for department in departments:
                services = department.services.all()
                service_names = [service.name for service in services]
                service_to_supervise = []  # Services in this department needing supervision

                # Find department director
                dept_director = department.collaborators.filter(role='department_director').first()
                dept_director_name = f"{dept_director.first_name} {dept_director.last_name}" if dept_director else None

                department_total_collaborators = 0

                total_participation_week_possible_department = 0
                total_participation_month_possible_department = 0

                department_submissions_day = 0
                department_submissions_week = 0
                department_submissions_month = 0
                department_participation_day = 0
                department_participation_week = 0
                department_participation_month = 0

                total_emotion_degree_day_department = 0
                total_emotion_degree_week_department = 0
                total_emotion_degree_month_department = 0

                services_data = []

                for service in services:
                    service_collaborators = list(service.collaborators.all())
                    collaborators += service_collaborators
                    department_total_collaborators += len(service_collaborators)

                    collaborators_to_supervise = []
                    for collaborator in service.collaborators.all():
                        if (
                                collaborator.emotion_degree_this_week < 0
                                or collaborator.emotion_degree_this_month < 0
                                or sum(e.emotion_degree for e in collaborator.emotions.filter(date__date=today)) < 0
                        ):
                            collaborators_to_supervise.append(f"{collaborator.first_name} {collaborator.last_name}")

                    # Submissions
                    submissions_day = get_emotions_for_period(service_collaborators, 'day').count()
                    submissions_week = get_emotions_for_period(service_collaborators, 'week').count()
                    submissions_month = get_emotions_for_period(service_collaborators, 'month').count()

                    # Participation percentages
                    percent_day = min(1.0, submissions_day / (len(service_collaborators) * 2) if len(
                        service_collaborators) else 0) * 100
                    week_days = [today + timedelta(days=i - today.weekday()) for i in range(5)]
                    week_working_days = sum(1 for d in week_days if d.month == today.month)
                    week_possible = len(service_collaborators) * week_working_days * 2
                    percent_week = min(1.0, submissions_week / week_possible if week_possible > 0 else 0) * 100
                    _, last_day = monthrange(year, month)
                    month_working_days = sum(1 for i in range(1, last_day + 1) if weekday(year, month, i) < 5)
                    month_possible = len(service_collaborators) * month_working_days * 2
                    percent_month = min(1.0, submissions_month / month_possible if month_possible > 0 else 0) * 100

                    total_participation_week_possible_department += week_possible
                    total_participation_month_possible_department += month_possible

                    # Emotion degree
                    degree_day = sum([e.emotion_degree for e in get_emotions_for_period(service_collaborators, 'day')])
                    degree_week = sum(
                        [e.emotion_degree for e in get_emotions_for_period(service_collaborators, 'week')])
                    degree_month = sum(
                        [e.emotion_degree for e in get_emotions_for_period(service_collaborators, 'month')])

                    humor_day = general_humor(degree_day)
                    humor_week = general_humor(degree_week)
                    humor_month = general_humor(degree_month)

                    # Aggregate totals for department
                    department_submissions_day += submissions_day
                    department_submissions_week += submissions_week
                    department_submissions_month += submissions_month
                    department_participation_day += percent_day
                    department_participation_week += percent_week
                    department_participation_month += percent_month

                    total_emotion_degree_day_department += degree_day
                    total_emotion_degree_week_department += degree_week
                    total_emotion_degree_month_department += degree_month

                    # For service_to_supervise
                    if humor_day == "negative" or humor_week == "negative" or humor_month == "negative":
                        service_to_supervise.append(service.name)

                    manager = service.collaborators.filter(role='manager').first()
                    employees = service.collaborators.filter(role='employee')

                    services_data.append({
                        'service_name': service.name,
                        'manager_name': f"{manager.first_name} {manager.last_name}" if manager else None,
                        'employees_names': [f"{emp.first_name} {emp.last_name}" for emp in employees],
                        'total_collaborators': len(service_collaborators),
                        'total_submissions_day': submissions_day,
                        'total_submissions_week': submissions_week,
                        'total_submissions_month': submissions_month,
                        'participation_percentage_day': round(percent_day, 2),
                        'participation_percentage_week': round(percent_week, 2),
                        'participation_percentage_month': round(percent_month, 2),
                        'general_humor_day': humor_day,
                        'general_humor_week': humor_week,
                        'general_humor_month': humor_month,
                        'collaborators_to_supervise': collaborators_to_supervise,
                    })

                # For total general humor: aggregate by majority
                def aggregate_general_humor(services_data, period):
                    humors = [service[f'general_humor_{period}'] for service in services_data]
                    count_positive = humors.count("positive")
                    count_negative = humors.count("negative")
                    return "positive" if count_positive > count_negative else (
                        "negative" if count_negative > count_positive else "neutral")

                departments_data.append({
                    'department_name': department.name,
                    'department_director_name': dept_director_name,
                    'service_names': service_names,
                    'services': services_data,
                    'total_collaborators': department_total_collaborators,
                    'total_participation_week_possible_department': total_participation_week_possible_department,
                    'total_participation_month_possible_department': total_participation_month_possible_department,
                    'total_submissions_day': department_submissions_day,
                    'total_submissions_week': department_submissions_week,
                    'total_submissions_month': department_submissions_month,
                    'unsubmitted_collaborators_week_department': total_participation_week_possible_department - department_submissions_week,
                    'unsubmitted_collaborators_month_department': total_participation_month_possible_department - department_submissions_month,
                    'percent_submission_week_department': round(department_submissions_week / total_participation_week_possible_department if total_participation_week_possible_department else 0, 2),
                    'percent_submission_month_department': round(department_submissions_month / total_participation_month_possible_department if total_participation_month_possible_department else 0, 2),
                    'participation_percentage_day': round(
                        department_participation_day / len(services) if len(services) else 0, 2),
                    'participation_percentage_week': round(
                        department_participation_week / len(services) if len(services) else 0, 2),
                    'participation_percentage_month': round(
                        department_participation_month / len(services) if len(services) else 0, 2),
                    'emotion_today_department': get_emotion_label(total_emotion_degree_day_department),
                    'emotion_week_department': get_emotion_label(total_emotion_degree_week_department),
                    'emotion_month_department': get_emotion_label(total_emotion_degree_month_department),
                    'general_humor_day': aggregate_general_humor(services_data, 'day'),
                    'general_humor_week': aggregate_general_humor(services_data, 'week'),
                    'general_humor_month': aggregate_general_humor(services_data, 'month'),
                    'service_to_supervise': service_to_supervise,
                })

                entity_total_collaborators += department_total_collaborators

                total_participation_week_possible_entity += total_participation_week_possible_department
                total_participation_month_possible_entity += total_participation_month_possible_department

                entity_submissions_day += department_submissions_day
                entity_submissions_week += department_submissions_week
                entity_submissions_month += department_submissions_month
                entity_participation_day += department_participation_day / len(services) if len(services) else 0
                entity_participation_week += department_participation_week / len(services) if len(services) else 0
                entity_participation_month += department_participation_month / len(services) if len(services) else 0

                total_emotion_degree_day_entity += total_emotion_degree_day_department
                total_emotion_degree_week_entity += total_emotion_degree_week_department
                total_emotion_degree_month_entity += total_emotion_degree_month_department

                if service_to_supervise:
                    department_to_supervise.append(department.name)

            def aggregate_general_humor(departments_data, period):
                humors = [dept[f'general_humor_{period}'] for dept in departments_data]
                count_positive = humors.count("positive")
                count_negative = humors.count("negative")
                return "positive" if count_positive > count_negative else (
                    "negative" if count_negative > count_positive else "neutral")

            entities_data.append({
                'entity_name': entity.name,
                'entity_director_name': entity_director_name,
                'department_names': department_names,
                'departments': departments_data,
                'total_collaborators': entity_total_collaborators,
                'total_participation_week_possible_entity': total_participation_week_possible_entity,
                'total_participation_month_possible_entity': total_participation_month_possible_entity,
                'total_submissions_day': entity_submissions_day,
                'total_submissions_week': entity_submissions_week,
                'total_submissions_month': entity_submissions_month,
                'unsubmitted_collaborators_week_entity': total_participation_week_possible_entity - entity_submissions_week,
                'unsubmitted_collaborators_month_entity': total_participation_month_possible_entity - entity_submissions_month,
                'percent_submission_week_entity': round(entity_submissions_week / total_participation_week_possible_entity if total_participation_week_possible_entity else 0, 2),
                'percent_submission_month_entity': round(entity_submissions_month / total_participation_month_possible_entity if total_participation_month_possible_entity else 0, 2),
                'participation_percentage_day': round(
                    entity_participation_day / len(departments) if len(departments) else 0, 2),
                'participation_percentage_week': round(
                    entity_participation_week / len(departments) if len(departments) else 0, 2),
                'participation_percentage_month': round(
                    entity_participation_month / len(departments) if len(departments) else 0, 2),
                'general_humor_day': aggregate_general_humor(departments_data, 'day'),
                'general_humor_week': aggregate_general_humor(departments_data, 'week'),
                'general_humor_month': aggregate_general_humor(departments_data, 'month'),

                'emotion_today_entity': get_emotion_label(total_emotion_degree_day_entity),
                'emotion_week_entity': get_emotion_label(total_emotion_degree_week_entity),
                'emotion_month_entity': get_emotion_label(total_emotion_degree_month_entity),

                'department_to_supervise': department_to_supervise,
            })

            total_collaborators += entity_total_collaborators
            total_submissions_day += entity_submissions_day
            total_submissions_week += entity_submissions_week
            total_submissions_month += entity_submissions_month
            total_participation_day += entity_participation_day / len(departments) if len(departments) else 0
            total_participation_week += entity_participation_week / len(departments) if len(departments) else 0
            total_participation_month += entity_participation_month / len(departments) if len(departments) else 0

            total_participation_week_possible += total_participation_week_possible_entity
            total_participation_month_possible += total_participation_month_possible_entity

            total_emotion_degree_day_cluster += total_emotion_degree_day_entity
            total_emotion_degree_week_cluster += total_emotion_degree_week_entity
            total_emotion_degree_month_cluster += total_emotion_degree_month_entity

            if department_to_supervise:
                entity_to_supervise.append(entity.name)

        def aggregate_general_humor(entities_data, period):
            humors = [ent[f'general_humor_{period}'] for ent in entities_data]
            count_positive = humors.count("positive")
            count_negative = humors.count("negative")
            return "positive" if count_positive > count_negative else (
                "negative" if count_negative > count_positive else "neutral")

        return Response({
            'cluster_name': cluster.name,
            'entity_names': entity_names,
            'num_entities': num_entities,
            'entities': entities_data,
            'total_collaborators': total_collaborators,
            'total_participation_week_possible': total_participation_week_possible,
            'total_participation_month_possible': total_participation_month_possible,
            'total_submissions_day': total_submissions_day,
            'total_submissions_week': total_submissions_week,
            'total_submissions_month': total_submissions_month,
            'unsubmitted_collaborators_week': total_participation_week_possible - total_submissions_week,
            'unsubmitted_collaborators_month': total_participation_month_possible - total_submissions_month,
            'percent_submission_week': round(total_submissions_week / total_participation_week_possible if total_participation_week_possible else 0, 2),
            'percent_submission_month': round(total_submissions_month / total_participation_month_possible if total_participation_month_possible else 0, 2),
            'participation_percentage_day': round(total_participation_day / num_entities if num_entities else 0, 2),
            'participation_percentage_week': round(total_participation_week / num_entities if num_entities else 0, 2),
            'participation_percentage_month': round(total_participation_month / num_entities if num_entities else 0, 2),
            'general_humor_day': aggregate_general_humor(entities_data, 'day'),
            'general_humor_week': aggregate_general_humor(entities_data, 'week'),
            'general_humor_month': aggregate_general_humor(entities_data, 'month'),

            'emotion_today': get_emotion_label(total_emotion_degree_day_cluster),
            'emotion_week': get_emotion_label(total_emotion_degree_week_cluster),
            'emotion_month': get_emotion_label(total_emotion_degree_month_cluster),

            'entity_to_supervise': entity_to_supervise,

        })

    @action(detail=False, methods=['GET'], url_path='pole-director-reporting-pdf')
    def pole_director_reporting_pdf(self, request):
        director = request.user

        # Get the data as you do in pole_director_overview
        if director.role != 'pole_director':
            return Response({'error': 'You are not a pole director'}, status=status.HTTP_403_FORBIDDEN)

        cluster = director.cluster
        if not cluster:
            return Response({'error': 'No cluster assigned'}, status=status.HTTP_400_BAD_REQUEST)

        overview = self.pole_director_overview(request).data

        # Create PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="cluster_report.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
        styles = getSampleStyleSheet()
        elements = []

        # Custom styles
        title_style = ParagraphStyle(name='Title', fontSize=18, textColor=colors.HexColor("#002b49"), spaceAfter=12)
        header_style = ParagraphStyle(name='Header', fontSize=14, textColor=colors.black, spaceBefore=12, spaceAfter=6)
        normal_style = ParagraphStyle(name='Normal', fontSize=10, textColor=colors.black)
        bold_style = ParagraphStyle(name='Bold', fontSize=10, textColor=colors.black, spaceAfter=6, leading=14)

        # Title
        elements.append(Paragraph(f"Reporting – Pôle : {overview['cluster_name']}", title_style))
        elements.append(Spacer(1, 12))

        # General Stats Table
        general_data = [
            ['Nombre d’entités', overview['num_entities']],
            ['Total collaborateurs', overview['total_collaborators']],
            ['Totale des soumissions possible', overview['total_participation_month_possible']],
            ['Soumissions achevés',
             f"{overview['total_submissions_month']}"],
            ['Soumissions inachevés', overview['unsubmitted_collaborators_month']],
            ['Participation (%)',
             f"{overview['percent_submission_month']}"],
            ['Tendance emotionnelle', overview['emotion_month']],
        ]
        table = Table(general_data, colWidths=[7 * cm, 8 * cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#002b49")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f2f2f2")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 18))

        # Entity details
        elements.append(Paragraph("Détails des entités :", header_style))
        for entity in overview['entities']:
            data = [
                ['Nom de l’entité', entity['entity_name']],
                ['Directeur', entity['entity_director_name'] or 'Non assigné'],
                ['Départements', ', '.join(entity['department_names'])],
                ['Total collaborateurs', entity['total_collaborators']],
                ['Total de soumissions possible', entity['total_participation_month_possible_entity']],
                ['Soumissions achevés',
                 f"{entity['total_submissions_month']}"],
                ['Soumissions inachevés', entity['unsubmitted_collaborators_month_entity']],
                ['Taux de participation %',
                 f"{entity['percent_submission_month_entity']}"],
                ['Tendance emotionnelle', entity['emotion_month_entity']],
                ['À superviser', ', '.join(entity['department_to_supervise']) or '—']
            ]
            entity_table = Table(data, colWidths=[6.5 * cm, 8.5 * cm])
            entity_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#dce3ea")),
                ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ]))
            elements.append(entity_table)
            elements.append(Spacer(1, 12))

            # Department details
            elements.append(Paragraph("Départements :", bold_style))
            for department in entity['departments']:
                dept_data = [
                    ['Nom du département', department['department_name']],
                    ['Directeur', department['department_director_name'] or 'Non assigné'],
                    ['Services', ', '.join(department['service_names'])],
                    ['Total collaborateurs', department['total_collaborators']],
                    ['Total de soumissions', department['total_participation_month_possible_department']],
                    ['Soumissions achevés',
                     f"{department['total_submissions_month']}"],
                    ['Soumissions inachevés', department['unsubmitted_collaborators_month_department']],
                    ['Taux de participation %',
                     f"{department['percent_submission_month_department']}"],
                    ['Tendance emotionnelle', department['emotion_month_department']],
                    ['À superviser', ', '.join(department['service_to_supervise']) or '—']
                ]
                dept_table = Table(dept_data, colWidths=[6.5 * cm, 8.5 * cm])
                dept_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f0f4f8")),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
                    ('GRID', (0, 0), (-1, -1), 0.2, colors.lightgrey),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ]))
                elements.append(dept_table)
                elements.append(Spacer(1, 10))

        # Footer: entities to supervise
        elements.append(Paragraph("Entités à superviser :", header_style))
        entity_list = ', '.join(overview['entity_to_supervise']) or 'Aucune'
        elements.append(Paragraph(entity_list, normal_style))

        doc.build(elements)
        return response


class DrhOverviewSet(viewsets.ViewSet):
    """
    Vue global pour le DRH
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['GET'], url_path='drh-overview')
    def drh_overview(self, request):
        drh = request.user

        # vérifier si drh ou pas
        if drh.role != 'admin':
            return Response({'error': "Vous n'êtes pas un DRH"}, status=status.HTTP_403_FORBIDDEN)

        clusters = Cluster.objects.all()
        num_clusters = clusters.count()
        cluster_names = [cluster.name for cluster in clusters]

        # Metriques du groupe Axian
        axian_collaborators = 0

        total_participation_week_possible = 0
        total_participation_month_possible = 0

        total_submissions_day = 0
        total_submissions_week = 0
        total_submissions_month = 0
        total_participation_day = 0
        total_participation_week = 0
        total_participation_month = 0

        total_emotion_degree_day_axian = 0
        total_emotion_degree_week_axian = 0
        total_emotion_degree_month_axian = 0

        cluster_to_supervise = [] # clusters à superviser

        clusters_data = []

        for cluster in clusters:
            entities= cluster.entities.all()
            collaborators = []
            entity_names = [ent.name for ent in entities]
            entity_to_supervise = []

            cluster_director = cluster.collaborators.filter(role='pole_director').first()
            cluster_director_name = f"{cluster_director.first_name} {cluster_director.last_name}" if cluster_director else None

            cluster_total_collaborators = 0

            total_participation_week_possible_cluster = 0
            total_participation_month_possible_cluster = 0

            cluster_submissions_day = 0
            cluster_submissions_week = 0
            cluster_submissions_month = 0
            cluster_participation_day = 0
            cluster_participation_week = 0
            cluster_participation_month = 0

            total_emotion_degree_day_cluster = 0
            total_emotion_degree_week_cluster = 0
            total_emotion_degree_month_cluster = 0

            entities_data = []

            for entity in entities:
                departments = entity.departments.all()
                department_names = [department.name for department in departments]
                department_to_supervise = []

                ent_director = entity.collaborators.filter(role='entity_director').first()
                ent_director_name = f"{ent_director.first_name} {ent_director.last_name}" if ent_director else None

                entity_total_collaborators = 0

                total_participation_week_possible_entity = 0
                total_participation_month_possible_entity = 0

                entity_submissions_day = 0
                entity_submissions_week = 0
                entity_submissions_month = 0
                entity_participation_day = 0
                entity_participation_week = 0
                entity_participation_month = 0

                total_emotion_degree_day_entity = 0
                total_emotion_degree_week_entity = 0
                total_emotion_degree_month_entity = 0

                departments_data = []

                for department in departments:
                    services = department.services.all()
                    service_names = [service.name for service in services]
                    service_to_supervise = []

                    dept_director = department.collaborators.filter(role='department_director').first()
                    dept_director_name = f"{dept_director.first_name} {dept_director.last_name}" if dept_director else None

                    department_total_collaborators = 0

                    total_participation_week_possible_department = 0
                    total_participation_month_possible_department = 0

                    department_submissions_day = 0
                    department_submissions_week = 0
                    department_submissions_month = 0
                    department_participation_day = 0
                    department_participation_week = 0
                    department_participation_month = 0

                    total_emotion_degree_day_department = 0
                    total_emotion_degree_week_department = 0
                    total_emotion_degree_month_department = 0

                    services_data = []

                    for service in services:
                        service_collaborators = list(service.collaborators.all())
                        collaborators += service_collaborators
                        department_total_collaborators += len(service_collaborators)

                        collaborators_to_supervise = []
                        for collaborator in service.collaborators.all():
                            if (
                                collaborator.emotion_degree_this_week < 0
                                or collaborator.emotion_degree_this_month < 0
                                or sum(e.emotion_degree for e in collaborator.emotions.filter(date__date=today)) < 0
                            ):
                                collaborators_to_supervise.append(f"{collaborator.first_name} {collaborator.last_name}")

                        # Submissions
                        submissions_day = get_emotions_for_period(service_collaborators, 'day').count()
                        submissions_week = get_emotions_for_period(service_collaborators, 'week').count()
                        submissions_month = get_emotions_for_period(service_collaborators, 'month').count()

                        # Paricipation percentages
                        percent_day = min(1.0, submissions_day / (len(service_collaborators) * 2) if len(
                            service_collaborators) else 0) * 100
                        week_days = [today + timedelta(days=i - today.weekday()) for i in range(5)]
                        week_working_days = sum(1 for d in week_days if d.month == today.month)
                        week_possible = len(service_collaborators) * week_working_days * 2
                        percent_week = min(1.0, submissions_week / week_possible if week_possible > 0 else 0) * 100
                        _, last_day = monthrange(year, month)
                        month_working_days = sum(1 for i in range(1, last_day + 1) if weekday(year, month, i) < 5)
                        month_possible = len(service_collaborators) * month_working_days * 2
                        percent_month = min(1.0, submissions_month / month_possible if month_possible > 0 else 0) * 100

                        total_participation_week_possible_department += week_possible
                        total_participation_month_possible_department += month_possible

                        # Emotion degree
                        degree_day = sum(
                            [e.emotion_degree for e in get_emotions_for_period(service_collaborators, 'day')])
                        degree_week = sum(
                            [e.emotion_degree for e in get_emotions_for_period(service_collaborators, 'week')])
                        degree_month = sum(
                            [e.emotion_degree for e in get_emotions_for_period(service_collaborators, 'month')])

                        humor_day = general_humor(degree_day)
                        humor_week = general_humor(degree_week)
                        humor_month = general_humor(degree_month)

                        # Aggregate for department
                        department_submissions_day += submissions_day
                        department_submissions_week += submissions_week
                        department_submissions_month += submissions_month
                        department_participation_day += percent_day
                        department_participation_week += percent_week
                        department_participation_month += percent_month

                        total_emotion_degree_day_department += degree_day
                        total_emotion_degree_week_department += degree_week
                        total_emotion_degree_month_department += degree_month

                        # For service to supervise
                        if humor_day == "negative" or humor_week == "negative" or humor_month == "negative":
                            service_to_supervise.append(service.name)

                        manager = service.collaborators.filter(role='manager').first()
                        employees = service.collaborators.filter(role='employee')

                        services_data.append({
                            'service_name': service.name,
                            'manager_name': f"{manager.first_name} {manager.last_name}" if manager else None,
                            'employees_names': [f"{emp.first_name} {emp.last_name}" for emp in employees],
                            'total_collaborators': len(service_collaborators),
                            'total_submissions_day': submissions_day,
                            'total_submissions_week': submissions_week,
                            'total_submissions_month': submissions_month,
                            'participation_percentage_day': round(percent_day, 2),
                            'participation_percentage_week': round(percent_week, 2),
                            'participation_percentage_month': round(percent_month, 2),
                            'general_humor_day': humor_day,
                            'general_humor_week': humor_week,
                            'general_humor_month': humor_month,
                            'collaborators_to_supervise': collaborators_to_supervise,
                        })

                    # For total general humor: aggregate by majority
                    def aggregate_general_humor(services_data, period):
                        humors = [service[f'general_humor_{period}'] for service in services_data]
                        count_positive = humors.count("positive")
                        count_negative = humors.count("negative")
                        return "positive" if count_positive > count_negative else (
                            "negative" if count_negative > count_positive else "neutral"
                        )

                    departments_data.append({
                        'department_name': department.name,
                        'department_director_name': dept_director_name,
                        'service_names': service_names,
                        'services': services_data,
                        'total_collaborators': department_total_collaborators,
                        'total_participation_week_possible_department': total_participation_week_possible_department,
                        'total_participation_month_possible_department': total_participation_month_possible_department,
                        'total_submissions_day': department_submissions_day,
                        'total_submissions_week': department_submissions_week,
                        'total_submissions_month': department_submissions_month,
                        'unsubmitted_collaborators_week_department': total_participation_week_possible_department - department_submissions_week,
                        'unsubmitted_collaborators_month_department': total_participation_month_possible_department - department_submissions_month,
                        'percent_submission_week_department': round(
                            department_submissions_week / total_participation_week_possible_department if total_participation_week_possible_department else 0,
                            2),
                        'percent_submission_month_department': round(
                            department_submissions_month / total_participation_month_possible_department if total_participation_month_possible_department else 0,
                            2),
                        'participation_percentage_day': round(
                            department_participation_day / len(services) if len(services) else 0, 2),
                        'participation_percentage_week': round(
                            department_participation_week / len(services) if len(services) else 0, 2),
                        'participation_percentage_month': round(
                            department_participation_month / len(services) if len(services) else 0, 2),
                        'emotion_today_department': get_emotion_label(total_emotion_degree_day_department),
                        'emotion_week_department': get_emotion_label(total_emotion_degree_week_department),
                        'emotion_month_department': get_emotion_label(total_emotion_degree_month_department),
                        'general_humor_day': aggregate_general_humor(services_data, 'day'),
                        'general_humor_week': aggregate_general_humor(services_data, 'week'),
                        'general_humor_month': aggregate_general_humor(services_data, 'month'),
                        'service_to_supervise': service_to_supervise,
                    })

                    entity_total_collaborators += department_total_collaborators

                    total_participation_week_possible_entity += total_participation_week_possible_department
                    total_participation_month_possible_entity += total_participation_month_possible_department

                    entity_submissions_day += department_submissions_day
                    entity_submissions_week += department_submissions_week
                    entity_submissions_month += department_submissions_month
                    entity_participation_day += department_participation_day / len(services) if len(services) else 0
                    entity_participation_week += department_participation_week / len(services) if len(services) else 0
                    entity_participation_month += department_participation_month / len(services) if len(services) else 0

                    total_emotion_degree_day_entity += total_emotion_degree_day_department
                    total_emotion_degree_week_entity += total_emotion_degree_week_department
                    total_emotion_degree_month_entity += total_emotion_degree_month_department

                    if service_to_supervise:
                        department_to_supervise.append(department.name)

                def aggregate_general_humor(departments_data, period):
                    humors = [dept[f'general_humor_{period}'] for dept in departments_data]
                    count_positive = humors.count("positive")
                    count_negative = humors.count("negative")
                    return "positive" if count_positive > count_negative else (
                        "negative" if count_negative > count_positive else "neutral")

                entities_data.append({
                    'entity_name': entity.name,
                    'entity_director_name': ent_director_name,
                    'department_names': department_names,
                    'departments': departments_data,
                    'total_collaborators': entity_total_collaborators,
                    'total_participation_week_possible_entity': total_participation_week_possible_entity,
                    'total_participation_month_possible_entity': total_participation_month_possible_entity,
                    'total_submissions_day': entity_submissions_day,
                    'total_submissions_week': entity_submissions_week,
                    'total_submissions_month': entity_submissions_month,
                    'unsubmitted_collaborators_week_entity': total_participation_week_possible_entity - entity_submissions_week,
                    'unsubmitted_collaborators_month_entity': total_participation_month_possible_entity - entity_submissions_month,
                    'percent_submission_week_entity': round(
                        entity_submissions_week / total_participation_week_possible_entity if total_participation_week_possible_entity else 0,
                        2),
                    'percent_submission_month_entity': round(
                        entity_submissions_month / total_participation_month_possible_entity if total_participation_month_possible_entity else 0,
                        2),
                    'participation_percentage_day': round(
                        entity_participation_day / len(departments) if len(departments) else 0, 2),
                    'participation_percentage_week': round(
                        entity_participation_week / len(departments) if len(departments) else 0, 2),
                    'participation_percentage_month': round(
                        entity_participation_month / len(departments) if len(departments) else 0, 2),
                    'general_humor_day': aggregate_general_humor(departments_data, 'day'),
                    'general_humor_week': aggregate_general_humor(departments_data, 'week'),
                    'general_humor_month': aggregate_general_humor(departments_data, 'month'),

                    'emotion_today_entity': get_emotion_label(total_emotion_degree_day_entity),
                    'emotion_week_entity': get_emotion_label(total_emotion_degree_week_entity),
                    'emotion_month_entity': get_emotion_label(total_emotion_degree_month_entity),

                    'department_to_supervise': department_to_supervise,
                })

                cluster_total_collaborators += entity_total_collaborators
                cluster_submissions_day += entity_submissions_day
                cluster_submissions_week += entity_submissions_week
                cluster_submissions_month += entity_submissions_month
                cluster_participation_day += entity_participation_day / len(departments) if len(departments) else 0
                cluster_participation_week += entity_participation_week / len(departments) if len(departments) else 0
                cluster_participation_month += entity_participation_month / len(departments) if len(departments) else 0

                total_participation_week_possible_cluster += total_participation_week_possible_entity
                total_participation_month_possible_cluster += total_participation_month_possible_entity

                total_emotion_degree_day_cluster += total_emotion_degree_day_entity
                total_emotion_degree_week_cluster += total_emotion_degree_week_entity
                total_emotion_degree_month_cluster += total_emotion_degree_month_entity

                if department_to_supervise:
                    entity_to_supervise.append(entity.name)

            def aggregate_general_humor(entities_data, period):
                humors = [ent[f'general_humor_{period}'] for ent in entities_data]
                count_positive = humors.count("positive")
                count_negative = humors.count("negative")
                return "positive" if count_positive > count_negative else (
                    "negative" if count_negative > count_positive else "neutral")

            clusters_data.append({
                'cluster_name': cluster.name,
                'entity_names': entity_names,
                'cluster_director': cluster_director_name,
                'entities': entities_data,
                'total_collaborators': cluster_total_collaborators,
                'total_participation_week_possible_cluster': total_participation_week_possible_cluster,
                'total_participation_month_possible_cluster': total_participation_month_possible_cluster,
                'cluster_submissions_day': cluster_submissions_day,
                'cluster_submissions_week': cluster_submissions_week,
                'cluster_submissions_month': cluster_submissions_month,
                'unsubmitted_collaborators_week_cluster': total_participation_week_possible_cluster - cluster_submissions_week,
                'unsubmitted_collaborators_month_cluster': total_participation_month_possible_cluster - cluster_submissions_month,
                'percent_submissions_week_cluster': round(cluster_submissions_week / total_participation_week_possible_cluster if total_participation_week_possible_cluster else 0, 2),
                'percent_submissions_month_cluster': round(cluster_submissions_month / total_participation_month_possible_cluster if total_participation_month_possible_cluster else 0, 2),
                'emotion_today_cluster': get_emotion_label(total_emotion_degree_day_cluster),
                'emotion_week_cluster': get_emotion_label(total_emotion_degree_week_cluster),
                'emotion_month_cluster': get_emotion_label(total_emotion_degree_month_cluster),

                'entity_to_supervise': entity_to_supervise,
            })

            axian_collaborators += cluster_total_collaborators
            total_submissions_day += cluster_submissions_day
            total_submissions_week += cluster_submissions_week
            total_submissions_month += cluster_submissions_month
            total_participation_day += cluster_participation_day / len(entities) if len(entities) else 0
            total_participation_week += cluster_participation_week / len(entities) if len(entities) else 0
            total_participation_month += cluster_participation_month / len(entities) if len(entities) else 0

            total_participation_week_possible += total_participation_week_possible_cluster
            total_participation_month_possible += total_participation_month_possible_cluster

            total_emotion_degree_day_axian += total_emotion_degree_day_cluster
            total_emotion_degree_week_axian += total_emotion_degree_week_cluster
            total_emotion_degree_month_axian += total_emotion_degree_month_cluster

            if entity_to_supervise:
                cluster_to_supervise.append(cluster.name)

        def aggregate_general_humor(clusters_data, period):
            humors = [clu[f'general_humor_{period}'] for clu in clusters_data]
            count_positive = humors.count("positive")
            count_negative = humors.count("negative")
            return "positive" if count_positive > count_negative else (
                "negative" if count_negative > count_positive else "neutral")

        return Response({
            'cluster_names': cluster_names,
            'num_clusters': num_clusters,
            'clusters': clusters_data,
            'total_collaborators': axian_collaborators,
            'total_participation_week_possible': total_participation_week_possible,
            'total_participation_month_possible': total_participation_month_possible,
            'total_submissions_day': total_submissions_day,
            'total_submissions_week': total_submissions_week,
            'total_submissions_month': total_submissions_month,
            'unsubmitted_collaborators_week': total_participation_week_possible - total_submissions_week,
            'unsubmitted_collaborators_month': total_participation_month_possible - total_submissions_month,
            'percent_submission_week': round(
                total_submissions_week / total_participation_week_possible if total_participation_week_possible else 0,
                2),
            'percent_submission_month': round(
                total_submissions_month / total_participation_month_possible if total_participation_month_possible else 0,
                2),

            'emotion_today': get_emotion_label(total_emotion_degree_day_axian),
            'emotion_week': get_emotion_label(total_emotion_degree_week_axian),
            'emotion_month': get_emotion_label(total_emotion_degree_month_axian),

            'cluster_to_supervise': cluster_to_supervise,
        })

    @action(detail=False, methods=['GET'], url_path='drh-overview-reporting-pdf')
    def drh_reporting_pdf(self, request):
        drh = request.user

        if drh.role != 'admin':
            return Response({'error': "Vous n'êtes pas un DRH"}, status=status.HTTP_403_FORBIDDEN)

        overview = self.drh_overview(request).data

        # Create PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="drh_report.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
        styles = getSampleStyleSheet()
        elements = []

        # Custom styles
        title_style = ParagraphStyle(name='Title', fontSize=18, textColor=colors.HexColor("#002b49"), spaceAfter=12)
        header_style = ParagraphStyle(name='Header', fontSize=14, textColor=colors.black, spaceBefore=12, spaceAfter=6)
        normal_style = ParagraphStyle(name='Normal', fontSize=10, textColor=colors.black)
        bold_style = ParagraphStyle(name='Bold', fontSize=10, textColor=colors.black, spaceAfter=6, leading=14)

        # Title
        elements.append(Paragraph("Reporting Globale Emotiontracker Axian Group", title_style))
        elements.append(Spacer(1, 12))

        # General Stats table
        general_data = [
            ['Nombre de clusters', overview['num_clusters']],
            ['Total collaborateurs', overview['total_collaborators']],
            ['Totale de soumissions possible', overview['total_participation_month_possible']],
            ['Soumissions achevés', overview['total_submissions_month']],
            ['Soumissions inachevés', overview['unsubmitted_collaborators_month']],
            ['Taux de participation (%)', overview['percent_submission_month']],
            ['Tendance emotionnelle global', overview['emotion_month']],
        ]
        table = Table(general_data, colWidths=[7 * cm, 8 * cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#002b49")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f2f2f2")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 18))

        # Cluster details
        elements.append(Paragraph("Clusters :"), header_style)
        for cluster in overview['clusters']:
            data = [
                ['Nom', cluster['cluster_name']],
                ['Directeur', cluster['cluster_director']],
                ["Entités", ', '.join(cluster['entity_names'])],
                ['Total collaborateurs', cluster['total_collaborators']],
                ['Total de soumissions possible', cluster['total_participation_month_possible_cluster']],
                ['Soumissions achevés', cluster['cluster_submissions_month']],
                ['Soumissions inachevés', cluster['unsubmitted_collaborators_month_cluster']],
                ['Taux de participation (%)', cluster['percent_submissions_month_cluster']],
                ["Tendance émotionnelle", cluster['emotion_month_cluster']],
                ['À superviser', ', '.join(cluster['entity_to_supervise']) or '—'],
            ]
            cluster_table = Table(data, colWidths=[6.5 * cm, 8.5 * cm])
            cluster_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#dce3ea")),
                ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ]))
            elements.append(cluster_table)
            elements.append(Spacer(1, 12))