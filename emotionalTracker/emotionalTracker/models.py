from django.db import models
from django.db.models import Sum, Avg, Count, F
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta
import pytz
from calendar import monthrange


class EmotionType(models.Model):
    EMOTION_CHOICES = [
        ('HAPPY', 'Happy'),
        ('SAD', 'Sad'),
        ('NEUTRAL', 'Neutral'),
        ('ANGRY', 'Angry'),
        ('EXCITED', 'Excited'),
        ('ANXIOUS', 'Anxious'),
    ]

    # Mapping des émotions vers leurs degrés
    EMOTION_DEGREES = {
        'HAPPY': 1,
        'SAD': -1,
        'NEUTRAL': 0,
        'ANGRY': -5,
        'EXCITED': 5,
        'ANXIOUS': -2,
    }

    name = models.CharField(
        max_length=50,
        choices=EMOTION_CHOICES,
        unique=True
    )
    emoticon = models.CharField(max_length=20)
    degree = models.IntegerField(editable=False)  # Le degré sera automatiquement défini

    def clean(self):
        """
        Valide et définit automatiquement le degré en fonction du nom de l'émotion
        """
        if self.name not in self.EMOTION_DEGREES:
            raise ValidationError({
                'name': f'Emotion type must be one of: {", ".join(self.EMOTION_DEGREES.keys())}'
            })
        self.degree = self.EMOTION_DEGREES[self.name]

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (degree: {self.degree})"

    class Meta:
        verbose_name = "Emotion Type"
        verbose_name_plural = "Emotion Types"


class Cluster(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cluster"
        verbose_name_plural = "Clusters"

    def __str__(self):
        return self.name

    def get_emotions_average(self):
        """
        Calcule les moyennes des degrés d'émotions pour différentes périodes
        au niveau du cluster
        """
        current_date = timezone.now().date()  # 2025-07-10

        # Calcul pour aujourd'hui
        today_avg = self.collaborator_set.filter(
            emotion__date=current_date
        ).annotate(
            daily_avg=Avg('emotion__emotion_degree')
        ).aggregate(
            avg_degree=Avg('daily_avg'),
            collaborators_count=Count('id', distinct=True),
            teams_count=Count('team', distinct=True),
            companies_count=Count('company', distinct=True)
        )

        # Calcul pour la semaine
        start_of_week = current_date - timedelta(days=current_date.weekday())
        week_avg = self.collaborator_set.filter(
            emotion__date__range=[start_of_week, current_date]
        ).annotate(
            weekly_avg=Avg('emotion__emotion_degree')
        ).aggregate(
            avg_degree=Avg('weekly_avg'),
            collaborators_count=Count('id', distinct=True),
            teams_count=Count('team', distinct=True),
            companies_count=Count('company', distinct=True)
        )

        # Calcul pour le mois
        start_of_month = current_date.replace(day=1)
        month_avg = self.collaborator_set.filter(
            emotion__date__range=[start_of_month, current_date]
        ).annotate(
            monthly_avg=Avg('emotion__emotion_degree')
        ).aggregate(
            avg_degree=Avg('monthly_avg'),
            collaborators_count=Count('id', distinct=True),
            teams_count=Count('team', distinct=True),
            companies_count=Count('company', distinct=True)
        )

        # Statistiques globales du cluster
        total_stats = {
            'collaborators': self.collaborator_set.count(),
            'teams': self.team_set.count(),
            'companies': self.company_set.count(),
            'services': sum(team.service_set.count() for team in self.team_set.all())
        }

        return {
            'daily': {
                'average': round(today_avg['avg_degree'] or 0, 2),
                'date': current_date,
                'collaborators_count': today_avg['collaborators_count'],
                'teams_count': today_avg['teams_count'],
                'companies_count': today_avg['companies_count'],
                'participation_rate': round(
                    (today_avg['collaborators_count'] / total_stats['collaborators'] * 100) if total_stats[
                                                                                                   'collaborators'] > 0 else 0,
                    1),
                'period': 'Aujourd\'hui'
            },
            'weekly': {
                'average': round(week_avg['avg_degree'] or 0, 2),
                'start_date': start_of_week,
                'end_date': current_date,
                'collaborators_count': week_avg['collaborators_count'],
                'teams_count': week_avg['teams_count'],
                'companies_count': week_avg['companies_count'],
                'participation_rate': round(
                    (week_avg['collaborators_count'] / total_stats['collaborators'] * 100) if total_stats[
                                                                                                  'collaborators'] > 0 else 0,
                    1),
                'period': 'Cette semaine'
            },
            'monthly': {
                'average': round(month_avg['avg_degree'] or 0, 2),
                'start_date': start_of_month,
                'end_date': current_date,
                'collaborators_count': month_avg['collaborators_count'],
                'teams_count': month_avg['teams_count'],
                'companies_count': month_avg['companies_count'],
                'participation_rate': round(
                    (month_avg['collaborators_count'] / total_stats['collaborators'] * 100) if total_stats[
                                                                                                   'collaborators'] > 0 else 0,
                    1),
                'period': 'Ce mois'
            },
            'cluster_stats': total_stats
        }

    @property
    def emotions_summary(self):
        """
        Retourne un résumé formaté des moyennes d'émotions pour le cluster
        """
        averages = self.get_emotions_average()
        stats = averages['cluster_stats']

        summary = (
            f"Moyennes des émotions pour le cluster {self.name}\n"
            f"Structure: {stats['companies']} entreprises, {stats['teams']} équipes, "
            f"{stats['services']} services, {stats['collaborators']} collaborateurs\n\n"

            f"- Aujourd'hui ({averages['daily']['date']}):\n"
            f"  Moyenne: {averages['daily']['average']} "
            f"({self.get_emotion_status(averages['daily']['average'])['status']})\n"
            f"  Participation: {averages['daily']['collaborators_count']} collaborateurs "
            f"de {averages['daily']['teams_count']} équipes "
            f"dans {averages['daily']['companies_count']} entreprises "
            f"({averages['daily']['participation_rate']}%)\n"

            f"- Cette semaine ({averages['weekly']['start_date']} au {averages['weekly']['end_date']}):\n"
            f"  Moyenne: {averages['weekly']['average']} "
            f"({self.get_emotion_status(averages['weekly']['average'])['status']})\n"
            f"  Participation: {averages['weekly']['collaborators_count']} collaborateurs "
            f"de {averages['weekly']['teams_count']} équipes "
            f"dans {averages['weekly']['companies_count']} entreprises "
            f"({averages['weekly']['participation_rate']}%)\n"

            f"- Ce mois ({averages['monthly']['start_date']} au {averages['monthly']['end_date']}):\n"
            f"  Moyenne: {averages['monthly']['average']} "
            f"({self.get_emotion_status(averages['monthly']['average'])['status']})\n"
            f"  Participation: {averages['monthly']['collaborators_count']} collaborateurs "
            f"de {averages['monthly']['teams_count']} équipes "
            f"dans {averages['monthly']['companies_count']} entreprises "
            f"({averages['monthly']['participation_rate']}%)"
        )

        return summary

    def get_emotion_status(self, average):
        """
        Détermine le statut émotionnel basé sur la moyenne
        """
        if average <= -5:
            return {'status': 'ANGRY', 'description': 'Très négatif'}
        elif average <= -2:
            return {'status': 'ANXIOUS', 'description': 'Anxieux'}
        elif average <= -1:
            return {'status': 'SAD', 'description': 'Triste'}
        elif average == 0:
            return {'status': 'NEUTRAL', 'description': 'Neutre'}
        elif average > 0 and average < 5:
            return {'status': 'HAPPY', 'description': 'Positif'}
        else:
            return {'status': 'EXCITED', 'description': 'Excellent'}


class Company(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Entreprise"
        verbose_name_plural = "Entreprises"

    def __str__(self):
        return self.name

    def get_emotions_average(self):
        """
        Calcule les moyennes des degrés d'émotions pour différentes périodes
        au niveau de l'entreprise
        """
        current_date = timezone.now().date()  # 2025-07-10

        # Calcul pour aujourd'hui
        today_avg = self.collaborator_set.filter(
            emotion__date=current_date
        ).annotate(
            daily_avg=Avg('emotion__emotion_degree')
        ).aggregate(
            avg_degree=Avg('daily_avg'),
            collaborators_count=Count('id', distinct=True),
            teams_count=Count('team', distinct=True)
        )

        # Calcul pour la semaine
        start_of_week = current_date - timedelta(days=current_date.weekday())
        week_avg = self.collaborator_set.filter(
            emotion__date__range=[start_of_week, current_date]
        ).annotate(
            weekly_avg=Avg('emotion__emotion_degree')
        ).aggregate(
            avg_degree=Avg('weekly_avg'),
            collaborators_count=Count('id', distinct=True),
            teams_count=Count('team', distinct=True)
        )

        # Calcul pour le mois
        start_of_month = current_date.replace(day=1)
        month_avg = self.collaborator_set.filter(
            emotion__date__range=[start_of_month, current_date]
        ).annotate(
            monthly_avg=Avg('emotion__emotion_degree')
        ).aggregate(
            avg_degree=Avg('monthly_avg'),
            collaborators_count=Count('id', distinct=True),
            teams_count=Count('team', distinct=True)
        )

        # Statistiques globales de l'entreprise
        total_stats = {
            'collaborators': self.collaborator_set.count(),
            'teams': self.team_set.count(),
            'services': sum(team.service_set.count() for team in self.team_set.all())
        }

        return {
            'daily': {
                'average': round(today_avg['avg_degree'] or 0, 2),
                'date': current_date,
                'collaborators_count': today_avg['collaborators_count'],
                'teams_count': today_avg['teams_count'],
                'participation_rate': round(
                    (today_avg['collaborators_count'] / total_stats['collaborators'] * 100) if total_stats[
                                                                                                   'collaborators'] > 0 else 0,
                    1),
                'period': 'Aujourd\'hui'
            },
            'weekly': {
                'average': round(week_avg['avg_degree'] or 0, 2),
                'start_date': start_of_week,
                'end_date': current_date,
                'collaborators_count': week_avg['collaborators_count'],
                'teams_count': week_avg['teams_count'],
                'participation_rate': round(
                    (week_avg['collaborators_count'] / total_stats['collaborators'] * 100) if total_stats[
                                                                                                  'collaborators'] > 0 else 0,
                    1),
                'period': 'Cette semaine'
            },
            'monthly': {
                'average': round(month_avg['avg_degree'] or 0, 2),
                'start_date': start_of_month,
                'end_date': current_date,
                'collaborators_count': month_avg['collaborators_count'],
                'teams_count': month_avg['teams_count'],
                'participation_rate': round(
                    (month_avg['collaborators_count'] / total_stats['collaborators'] * 100) if total_stats[
                                                                                                   'collaborators'] > 0 else 0,
                    1),
                'period': 'Ce mois'
            },
            'company_stats': total_stats
        }

    @property
    def emotions_summary(self):
        """
        Retourne un résumé formaté des moyennes d'émotions pour l'entreprise
        """
        averages = self.get_emotions_average()
        stats = averages['company_stats']

        summary = (
            f"Moyennes des émotions pour {self.name}\n"
            f"Structure: {stats['teams']} équipes, {stats['services']} services, "
            f"{stats['collaborators']} collaborateurs\n\n"

            f"- Aujourd'hui ({averages['daily']['date']}):\n"
            f"  Moyenne: {averages['daily']['average']} "
            f"({self.get_emotion_status(averages['daily']['average'])['status']})\n"
            f"  Participation: {averages['daily']['collaborators_count']} collaborateurs "
            f"de {averages['daily']['teams_count']} équipes "
            f"({averages['daily']['participation_rate']}%)\n"

            f"- Cette semaine ({averages['weekly']['start_date']} au {averages['weekly']['end_date']}):\n"
            f"  Moyenne: {averages['weekly']['average']} "
            f"({self.get_emotion_status(averages['weekly']['average'])['status']})\n"
            f"  Participation: {averages['weekly']['collaborators_count']} collaborateurs "
            f"de {averages['weekly']['teams_count']} équipes "
            f"({averages['weekly']['participation_rate']}%)\n"

            f"- Ce mois ({averages['monthly']['start_date']} au {averages['monthly']['end_date']}):\n"
            f"  Moyenne: {averages['monthly']['average']} "
            f"({self.get_emotion_status(averages['monthly']['average'])['status']})\n"
            f"  Participation: {averages['monthly']['collaborators_count']} collaborateurs "
            f"de {averages['monthly']['teams_count']} équipes "
            f"({averages['monthly']['participation_rate']}%)"
        )

        return summary

    def get_emotion_status(self, average):
        """
        Détermine le statut émotionnel basé sur la moyenne
        """
        if average <= -5:
            return {'status': 'ANGRY', 'description': 'Très négatif'}
        elif average <= -2:
            return {'status': 'ANXIOUS', 'description': 'Anxieux'}
        elif average <= -1:
            return {'status': 'SAD', 'description': 'Triste'}
        elif average == 0:
            return {'status': 'NEUTRAL', 'description': 'Neutre'}
        elif average > 0 and average < 5:
            return {'status': 'HAPPY', 'description': 'Positif'}
        else:
            return {'status': 'EXCITED', 'description': 'Excellent'}


class Team(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    services = models.ManyToManyField('Service', related_name='teams')

    class Meta:
        verbose_name = "Équipe"
        verbose_name_plural = "Équipes"

    def __str__(self):
        return self.name

    def get_emotions_average(self):
        """
        Calcule les moyennes des degrés d'émotions pour différentes périodes
        """
        current_date = timezone.now().date()  # 2025-07-10

        # Calcul pour aujourd'hui
        today_avg = self.collaborator_set.filter(
            emotion__date=current_date
        ).annotate(
            daily_avg=Avg('emotion__emotion_degree')
        ).aggregate(
            avg_degree=Avg('daily_avg'),
            collaborators_count=Count('id', distinct=True)
        )

        # Calcul pour la semaine
        start_of_week = current_date - timedelta(days=current_date.weekday())
        week_avg = self.collaborator_set.filter(
            emotion__date__range=[start_of_week, current_date]
        ).annotate(
            weekly_avg=Avg('emotion__emotion_degree')
        ).aggregate(
            avg_degree=Avg('weekly_avg'),
            collaborators_count=Count('id', distinct=True)
        )

        # Calcul pour le mois
        start_of_month = current_date.replace(day=1)
        month_avg = self.collaborator_set.filter(
            emotion__date__range=[start_of_month, current_date]
        ).annotate(
            monthly_avg=Avg('emotion__emotion_degree')
        ).aggregate(
            avg_degree=Avg('monthly_avg'),
            collaborators_count=Count('id', distinct=True)
        )

        # Total des collaborateurs dans l'équipe
        total_collaborators = self.collaborator_set.count()

        return {
            'daily': {
                'average': round(today_avg['avg_degree'] or 0, 2),
                'date': current_date,
                'collaborators_count': today_avg['collaborators_count'],
                'participation_rate': round(
                    (today_avg['collaborators_count'] / total_collaborators * 100) if total_collaborators > 0 else 0,
                    1),
                'period': 'Aujourd\'hui'
            },
            'weekly': {
                'average': round(week_avg['avg_degree'] or 0, 2),
                'start_date': start_of_week,
                'end_date': current_date,
                'collaborators_count': week_avg['collaborators_count'],
                'participation_rate': round(
                    (week_avg['collaborators_count'] / total_collaborators * 100) if total_collaborators > 0 else 0, 1),
                'period': 'Cette semaine'
            },
            'monthly': {
                'average': round(month_avg['avg_degree'] or 0, 2),
                'start_date': start_of_month,
                'end_date': current_date,
                'collaborators_count': month_avg['collaborators_count'],
                'participation_rate': round(
                    (month_avg['collaborators_count'] / total_collaborators * 100) if total_collaborators > 0 else 0,
                    1),
                'period': 'Ce mois'
            },
            'team_size': total_collaborators
        }

    @property
    def emotions_summary(self):
        """
        Retourne un résumé formaté des moyennes d'émotions
        """
        averages = self.get_emotions_average()

        summary = (
            f"Moyennes des émotions pour l'équipe {self.name} "
            f"(Total: {averages['team_size']} collaborateurs):\n"

            f"- Aujourd'hui ({averages['daily']['date']}):\n"
            f"  Moyenne: {averages['daily']['average']} "
            f"({self.get_emotion_status(averages['daily']['average'])['status']})\n"
            f"  Participation: {averages['daily']['collaborators_count']} collaborateurs "
            f"({averages['daily']['participation_rate']}%)\n"

            f"- Cette semaine ({averages['weekly']['start_date']} au {averages['weekly']['end_date']}):\n"
            f"  Moyenne: {averages['weekly']['average']} "
            f"({self.get_emotion_status(averages['weekly']['average'])['status']})\n"
            f"  Participation: {averages['weekly']['collaborators_count']} collaborateurs "
            f"({averages['weekly']['participation_rate']}%)\n"

            f"- Ce mois ({averages['monthly']['start_date']} au {averages['monthly']['end_date']}):\n"
            f"  Moyenne: {averages['monthly']['average']} "
            f"({self.get_emotion_status(averages['monthly']['average'])['status']})\n"
            f"  Participation: {averages['monthly']['collaborators_count']} collaborateurs "
            f"({averages['monthly']['participation_rate']}%)"
        )

        return summary

    def get_emotion_status(self, average):
        """
        Détermine le statut émotionnel basé sur la moyenne
        """
        if average <= -5:
            return {'status': 'ANGRY', 'description': 'Très négatif'}
        elif average <= -2:
            return {'status': 'ANXIOUS', 'description': 'Anxieux'}
        elif average <= -1:
            return {'status': 'SAD', 'description': 'Triste'}
        elif average == 0:
            return {'status': 'NEUTRAL', 'description': 'Neutre'}
        elif average > 0 and average < 5:
            return {'status': 'HAPPY', 'description': 'Positif'}
        else:
            return {'status': 'EXCITED', 'description': 'Excellent'}


class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    team = models.ForeignKey('Team', on_delete=models.CASCADE)
    company = models.ForeignKey('Company', on_delete=models.CASCADE)
    cluster = models.ForeignKey('Cluster', on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Service"
        verbose_name_plural = "Services"

    def __str__(self):
        return self.name

    def get_emotions_average(self):
        """
        Calcule les moyennes des degrés d'émotions pour différentes périodes
        """
        current_date = timezone.now().date()  # 2025-07-10

        # Calcul pour aujourd'hui
        today_avg = self.team.collaborator_set.filter(
            emotion__date=current_date
        ).annotate(
            daily_avg=Avg('emotion__emotion_degree')
        ).aggregate(
            avg_degree=Avg('daily_avg'),
            collaborators_count=Count('id', distinct=True)
        )

        # Calcul pour la semaine
        start_of_week = current_date - timedelta(days=current_date.weekday())  # Lundi
        week_avg = self.team.collaborator_set.filter(
            emotion__date__range=[start_of_week, current_date]
        ).annotate(
            weekly_avg=Avg('emotion__emotion_degree')
        ).aggregate(
            avg_degree=Avg('weekly_avg'),
            collaborators_count=Count('id', distinct=True)
        )

        # Calcul pour le mois
        start_of_month = current_date.replace(day=1)  # Premier jour du mois
        month_avg = self.team.collaborator_set.filter(
            emotion__date__range=[start_of_month, current_date]
        ).annotate(
            monthly_avg=Avg('emotion__emotion_degree')
        ).aggregate(
            avg_degree=Avg('monthly_avg'),
            collaborators_count=Count('id', distinct=True)
        )

        return {
            'daily': {
                'average': round(today_avg['avg_degree'] or 0, 2),
                'date': current_date,
                'collaborators_count': today_avg['collaborators_count'],
                'period': 'Aujourd\'hui'
            },
            'weekly': {
                'average': round(week_avg['avg_degree'] or 0, 2),
                'start_date': start_of_week,
                'end_date': current_date,
                'collaborators_count': week_avg['collaborators_count'],
                'period': 'Cette semaine'
            },
            'monthly': {
                'average': round(month_avg['avg_degree'] or 0, 2),
                'start_date': start_of_month,
                'end_date': current_date,
                'collaborators_count': month_avg['collaborators_count'],
                'period': 'Ce mois'
            }
        }

    @property
    def emotions_summary(self):
        """
        Retourne un résumé formaté des moyennes d'émotions
        """
        averages = self.get_emotions_average()

        summary = (
            f"Moyennes des émotions pour {self.name}:\n"
            f"- Aujourd'hui ({averages['daily']['date']}): "
            f"{averages['daily']['average']} "
            f"({averages['daily']['collaborators_count']} collaborateurs)\n"

            f"- Cette semaine ({averages['weekly']['start_date']} au {averages['weekly']['end_date']}): "
            f"{averages['weekly']['average']} "
            f"({averages['weekly']['collaborators_count']} collaborateurs)\n"

            f"- Ce mois ({averages['monthly']['start_date']} au {averages['monthly']['end_date']}): "
            f"{averages['monthly']['average']} "
            f"({averages['monthly']['collaborators_count']} collaborateurs)"
        )

        return summary

    def get_emotion_status(self, average):
        """
        Détermine le statut émotionnel basé sur la moyenne
        """
        if average <= -5:
            return {'status': 'ANGRY', 'description': 'Très négatif'}
        elif average <= -2:
            return {'status': 'ANXIOUS', 'description': 'Anxieux'}
        elif average <= -1:
            return {'status': 'SAD', 'description': 'Triste'}
        elif average == 0:
            return {'status': 'NEUTRAL', 'description': 'Neutre'}
        elif average > 0 and average < 5:
            return {'status': 'HAPPY', 'description': 'Positif'}
        else:
            return {'status': 'EXCITED', 'description': 'Excellent'}


class Collaborator(AbstractUser):
    ROLE_CHOICES = [
        ('EMPLOYEE', 'Employé'),
        ('MANAGER', 'Manager'),
        ('DIRECTOR', 'Directeur'),
        ('POLE_DIRECTOR', 'Directeur de Pôle')
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='EMPLOYEE'
    )

    team = models.ForeignKey(
        'Team',
        on_delete=models.SET_NULL,
        null=True,
        related_name='team_members'
    )
    company = models.ForeignKey(
        'Company',
        on_delete=models.SET_NULL,
        null=True
    )
    cluster = models.ForeignKey(
        'Cluster',
        on_delete=models.SET_NULL,
        null=True
    )
    # is_manager = models.BooleanField(default=False)
    manager = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinates'
    )

    class Meta:
        verbose_name = "Collaborateur"
        verbose_name_plural = "Collaborateurs"

    def clean(self):
        """
        Validation personnalisée pour s'assurer que la hiérarchie est respectée
        """
        if self.manager:
            # Un employé ne peut avoir qu'un manager comme supérieur
            if self.role == 'EMPLOYEE' and self.manager.role != 'MANAGER':
                raise ValidationError('Un employé doit avoir un manager comme supérieur')

            # Un manager ne peut avoir qu'un directeur comme supérieur
            if self.role == 'MANAGER' and self.manager.role != 'DIRECTOR':
                raise ValidationError('Un manager doit avoir un directeur comme supérieur')

            # Un directeur ne peut avoir qu'un directeur de pôle comme supérieur
            if self.role == 'DIRECTOR' and self.manager.role != 'POLE_DIRECTOR':
                raise ValidationError('Un directeur doit avoir un directeur de pôle comme supérieur')

            # Un directeur de pôle ne peut pas avoir de supérieur
            if self.role == 'POLE_DIRECTOR' and self.manager:
                raise ValidationError('Un directeur de pôle ne peut pas avoir de supérieur')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_role_display()})"

    @property
    def today_morning_emotion(self):
        """
        Retourne l'émotion du collaborateur pour le matin du jour actuel
        Returns:
            Emotion object or None si aucune émotion n'a été soumise
        """
        today = timezone.now().date()
        try:
            return self.emotion_set.get(
                date=today,
                period='DAY'
            )
        except Emotion.DoesNotExist:
            return None

    @property
    def today_morning_emotion_status(self):
        """
        Retourne un statut formaté de l'émotion du matin
        """
        emotion = self.today_morning_emotion
        if emotion is None:
            return "Pas encore d'émotion soumise ce matin"

        return (
            f"Emotion du matin: {emotion.emotion_type.name} "
            f"(Degré: {emotion.emotion_degree}, {emotion.emotion_status})"
        )

    @property
    def has_submitted_morning_emotion(self):
        """
        Vérifie si le collaborateur a déjà soumis une émotion ce matin
        """
        return self.today_morning_emotion is not None

    @property
    def weekly_emotion_summary(self):
        """
        Calcule la somme des degrés d'émotions pour la semaine en cours,
        en séparant le jour actuel du reste de la semaine
        """
        today = timezone.now().date()
        # Début de la semaine (Lundi)
        start_of_week = today - timedelta(days=today.weekday())

        # Calcul pour aujourd'hui
        today_emotions = self.emotion_set.filter(date=today).aggregate(
            total_degree=Sum('emotion_degree')
        )
        today_sum = today_emotions['total_degree'] or 0

        # Calcul pour le reste de la semaine (du lundi jusqu'à hier)
        rest_of_week_emotions = self.emotion_set.filter(
            date__range=[start_of_week, today - timedelta(days=1)]
        ).aggregate(
            total_degree=Sum('emotion_degree')
        )
        rest_of_week_sum = rest_of_week_emotions['total_degree'] or 0

        # Calcul du total
        total_sum = today_sum + rest_of_week_sum
        weekly_emotion = self.get_weekly_emotion_type()

        return {
            'today_sum': today_sum,
            'rest_of_week_sum': rest_of_week_sum,
            'total_sum': total_sum,
            'start_date': start_of_week,
            'end_date': today,
            'weekly_emotion': weekly_emotion
        }

    @property
    def weekly_emotion_status(self):
        """
        Retourne un statut formaté des émotions de la semaine
        """
        summary = self.weekly_emotion_summary
        weekly_emotion = summary['weekly_emotion']

        status = (
            f"Émotions du {summary['start_date'].strftime('%d/%m/%Y')} "
            f"au {summary['end_date'].strftime('%d/%m/%Y')}:\n"
            f"- Aujourd'hui: {summary['today_sum']}\n"
            f"- Reste de la semaine: {summary['rest_of_week_sum']}\n"
            f"- Total: {summary['total_sum']}"
            f"- Bilan: {weekly_emotion['description']} ({weekly_emotion['type']})"
        )

        return status

    @property
    def monthly_emotion_summary(self):
        """
        Calcule la somme des degrés d'émotions pour le mois en cours,
        en séparant le jour actuel du reste du mois
        """
        today = timezone.now().date()
        first_day_of_month = today.replace(day=1)

        # Calcul pour aujourd'hui
        today_emotions = self.emotion_set.filter(date=today).aggregate(
            total_degree=Sum('emotion_degree')
        )
        today_sum = today_emotions['total_degree'] or 0

        # Calcul pour le reste du mois (du premier jour jusqu'à hier)
        rest_of_month_emotions = self.emotion_set.filter(
            date__range=[first_day_of_month, today - timedelta(days=1)]
        ).aggregate(
            total_degree=Sum('emotion_degree')
        )
        rest_of_month_sum = rest_of_month_emotions['total_degree'] or 0

        # Calcul du total
        total_sum = today_sum + rest_of_month_sum

        # Déterminer le type d'émotion mensuelle
        monthly_emotion = self.get_monthly_emotion_type(total_sum)

        return {
            'today_sum': today_sum,
            'rest_of_month_sum': rest_of_month_sum,
            'total_sum': total_sum,
            'start_date': first_day_of_month,
            'end_date': today,
            'monthly_emotion': monthly_emotion,
            'month_name': today.strftime('%B %Y')
        }

    @property
    def monthly_emotion_status(self):
        """
        Retourne un statut formaté des émotions du mois
        """
        summary = self.monthly_emotion_summary
        monthly_emotion = summary['monthly_emotion']

        status = (
            f"Émotions de {summary['month_name']}:\n"
            f"- Aujourd'hui: {summary['today_sum']}\n"
            f"- Reste du mois: {summary['rest_of_month_sum']}\n"
            f"- Total: {summary['total_sum']}\n"
            f"- Bilan: {monthly_emotion['description']} ({monthly_emotion['type']})"
        )

        return status

    @property
    def emotion_trends(self):
        """
        Retourne les tendances émotionnelles pour la semaine et le mois
        """
        weekly = self.weekly_emotion_summary
        monthly = self.monthly_emotion_summary

        return {
            'week': {
                'total': weekly['total_sum'],
                'emotion': weekly['weekly_emotion']
            },
            'month': {
                'total': monthly['total_sum'],
                'emotion': monthly['monthly_emotion']
            }
        }

    @property
    def is_employee(self):
        return self.role == 'EMPLOYEE'

    @property
    def is_manager(self):
        return self.role == 'MANAGER'

    @property
    def is_director(self):
        return self.role == 'DIRECTOR'

    @property
    def is_pole_director(self):
        return self.role == 'POLE_DIRECTOR'

    def get_subordinates(self):
        """
        Retourne tous les subordonnés directs du collaborateur
        """
        return self.subordinates.all()

    def get_all_subordinates(self):
        """
        Retourne tous les subordonnés (directs et indirects) du collaborateur
        """
        all_subordinates = []
        direct_subordinates = self.get_subordinates()

        for subordinate in direct_subordinates:
            all_subordinates.append(subordinate)
            all_subordinates.extend(subordinate.get_all_subordinates())

        return all_subordinates

    def get_emotion_trend(self):
        """
        Détermine la tendance émotionnelle de la semaine
        """
        summary = self.weekly_emotion_summary
        if summary['total_sum'] > 0:
            return "Positive"
        elif summary['total_sum'] < 0:
            return "Négative"
        return "Neutre"

    def get_weekly_emotion_type(self):
        """
        Détermine le type d'émotion hebdomadaire basé sur la somme totale des degrés
        Rules:
        - <= -5 : "angry"
        - <= -2 : "anxious"
        - <= -1 : "sad"
        - = 0   : "neutral"
        - > 0 et < 5 : "happy"
        - >= 5  : "excited"
        """
        summary = self.weekly_emotion_summary
        total_degree = summary['total_sum']

        if total_degree <= -5:
            return {
                'type': 'ANGRY',
                'degree': -5,
                'description': 'Semaine très négative'
            }
        elif total_degree <= -2:
            return {
                'type': 'ANXIOUS',
                'degree': -2,
                'description': 'Semaine anxieuse'
            }
        elif total_degree <= -1:
            return {
                'type': 'SAD',
                'degree': -1,
                'description': 'Semaine triste'
            }
        elif total_degree == 0:
            return {
                'type': 'NEUTRAL',
                'degree': 0,
                'description': 'Semaine neutre'
            }
        elif total_degree > 0 and total_degree < 5:
            return {
                'type': 'HAPPY',
                'degree': 1,
                'description': 'Semaine positive'
            }
        else:  # >= 5
            return {
                'type': 'EXCITED',
                'degree': 5,
                'description': 'Semaine excellente'
            }

    def get_monthly_emotion_type(self, total_degree):
        """
        Détermine le type d'émotion mensuelle basé sur la somme totale des degrés
        """
        if total_degree <= -5:
            return {
                'type': 'ANGRY',
                'degree': -5,
                'description': 'Mois très négatif'
            }
        elif total_degree <= -2:
            return {
                'type': 'ANXIOUS',
                'degree': -2,
                'description': 'Mois anxieux'
            }
        elif total_degree <= -1:
            return {
                'type': 'SAD',
                'degree': -1,
                'description': 'Mois triste'
            }
        elif total_degree == 0:
            return {
                'type': 'NEUTRAL',
                'degree': 0,
                'description': 'Mois neutre'
            }
        elif total_degree > 0 and total_degree < 5:
            return {
                'type': 'HAPPY',
                'degree': 1,
                'description': 'Mois positif'
            }
        else:  # >= 5
            return {
                'type': 'EXCITED',
                'degree': 5,
                'description': 'Mois excellent'
            }


class Emotion(models.Model):
    PERIOD_CHOICES = [
        ('MORNING', 'Morning'),
        ('EVENING', 'Evening'),
    ]

    collaborator = models.ForeignKey(Collaborator, on_delete=models.CASCADE)
    emotion_type = models.ForeignKey(EmotionType, on_delete=models.CASCADE)
    emotion_degree = models.IntegerField(
        editable=False,
        help_text="Degré d'émotion déterminé automatiquement par le type d'émotion"
    )
    date = models.DateField()
    submission_time = models.TimeField(auto_now_add=True)  # Nouveau champ pour l'heure de soumission
    period = models.CharField(
        max_length=10,
        choices=PERIOD_CHOICES,
        editable=False  # Le champ ne sera pas modifiable manuellement
    )
    comment = models.TextField(blank=True, null=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['collaborator', 'date', 'period']
        ordering = ['-date', '-created_at']
        verbose_name = "Émotion"
        verbose_name_plural = "Émotions"

    def __str__(self):
        return f"{self.collaborator} - {self.date} ({self.get_period_display()})"

    def determine_period(self):
        """
        Détermine la période (jour/soir) en fonction de l'heure de soumission
        """
        if self.submission_time.hour < 12:
            return 'DAY'
        return 'EVENING'

    def update_emotion_degree(self):
        """
        Met à jour le degré d'émotion en fonction du type d'émotion
        """
        self.emotion_degree = self.emotion_type.degree

    @property
    def emotion_status(self):
        """
        Retourne un statut lisible basé sur le degré d'émotion
        """
        if self.emotion_degree > 0:
            return "Positif"
        elif self.emotion_degree < 0:
            return "Négatif"
        return "Neutre"

    @property
    def relative_period(self):
        """
        Retourne la période relative de l'émotion par rapport à la date actuelle
        """
        today = timezone.now().date()
        emotion_date = self.date

        if emotion_date == today:
            return "ce jour"

        # Calcul du début de la semaine (lundi)
        current_week_start = today - timedelta(days=today.weekday())
        if current_week_start <= emotion_date <= today:
            return "cette semaine"

        # Vérification si même mois
        if emotion_date.year == today.year and emotion_date.month == today.month:
            return "ce mois"

        # Vérification si même année
        if emotion_date.year == today.year:
            return "cette année"

        return f"année {emotion_date.year}"

    @property
    def formatted_date(self):
        """
        retourne la date formatée avec la période relative et jour/soir
         """
        period_str = "matin" if self.period == 'DAY' else "soir"
        return f"{self.date.strftime('%d/%m/%Y')} ({period_str}, {self.relative_period})"

    @property
    def submission_period(self):
        """
        Retourne une description lisible de la période de soumission
        """
        return "Jour" if self.period == 'DAY' else "Soir"

    def clean(self):
        """
        Validation personnalisée
        """
        if self.pk is None:  # Seulement pour les nouvelles émotions
            existing = Emotion.objects.filter(
                collaborator=self.collaborator,
                date=self.date,
                period=self.determine_period()
            ).exists()

            if existing:
                raise ValidationError(
                    f"Vous avez déjà soumis une émotion pour cette période ({self.submission_period}) aujourd'hui"
                )

    def save(self, *args, **kwargs):
        if not self.date:
            self.date = timezone.now().date()

        # Définir la période en fonction de l'heure
        self.period = self.determine_period()

        # Mettre à jour le degré d'émotion
        self.update_emotion_degree()

        self.clean()
        super().save(*args, **kwargs)


