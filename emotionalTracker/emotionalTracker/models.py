from django.db import models
from django.db.models import Sum, Avg, Count, F
from django.contrib.auth.models import AbstractUser, Group, Permission, AbstractBaseUser, PermissionsMixin, BaseUserManager
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

    id = models.AutoField(primary_key=True)
    emoticon = models.CharField(max_length=20)
    degree = models.IntegerField(editable=False)  # Le degré sera automatiquement défini
    created_at = models.DateTimeField(auto_now_add=True)

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
    """Premier niveau de l'organisation (ex: Groupe, Holding, Région)"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Entity(models.Model):
    """Deuxième niveau (ex: Filiale, Société, Site)"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE, related_name='entities')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Department(models.Model):
    """Troisième niveau (ex: Département, Direction, Business Unit)"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name='departments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('name', 'entity')

    def __str__(self):
        return f"{self.name} ({self.entity.name})"


class Service(models.Model):
    """Quatrième niveau (ex: Service, Équipe, Cellule)"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='services')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('name', 'department')

    def __str__(self):
        return f"{self.name} ({self.department.name})"


class CollaboratorManager(BaseUserManager):
    def create_user(self, email_address, first_name, last_name, password=None, **extra_fields):
        if not email_address:
            raise ValueError('L’adresse email est obligatoire')
        email_address = self.normalize_email(email_address)
        user = self.model(
            email_address=email_address,
            first_name=first_name,
            last_name=last_name,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email_address, first_name, last_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email_address, first_name, last_name, password, **extra_fields)


class Collaborator(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('employee', 'Employé'),
        ('manager', 'Manager'),
        ('director', 'Directeur'),
        ('pole_directeur', 'Directeur de Pôle'),
    ]

    id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email_address = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    service = models.ForeignKey('Service', on_delete=models.CASCADE, related_name="collaborators")
    manager = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='subordinates',
        help_text="Manager du collaborateur"
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = CollaboratorManager()

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.role})"


class Emotion(models.Model):
    HALF_DAY_CHOICES = [
        ('morning', 'Morning'),
        ('evening', 'Evening'),
    ]

    id = models.AutoField(primary_key=True)
    emotion_type = models.ForeignKey('EmotionType', on_delete=models.CASCADE, related_name="emotions")
    emotion_degree = models.IntegerField(editable=False)
    collaborator = models.ForeignKey('Collaborator', on_delete=models.CASCADE, related_name="emotions")
    date = models.DateTimeField(default=timezone.now)
    week_number = models.PositiveIntegerField(editable=False)
    month = models.PositiveIntegerField(editable=False)
    year = models.PositiveIntegerField(editable=False)
    half_day = models.CharField(max_length=10, choices=HALF_DAY_CHOICES, editable=False)
    date_period = models.CharField(max_length=20, editable=False)

    def save(self, *args, **kwargs):
        # Set degree from emotion_type
        if self.emotion_type:
            self.emotion_degree = self.emotion_type.degree

        # set date_related fields
        dt = self.date if self.date else timezone.now()
        self.week_number = dt.isocalendar()[1]
        self.month = dt.month
        self.year = dt.year

        # set half_day
        self.half_day = "morning" if dt.hour < 12 else "evening"

        # set date_period
        today = timezone.localdate()
        submitted_date = dt.date()
        if submitted_date == today:
            self.date_period = 'ce jour'
        elif submitted_date.isocalendar()[1] == today.isocalendar()[1] and submitted_date.year == today.year:
            self.date_period = "cette semaine"
        elif submitted_date.month == today.month and submitted_date.year == today.year:
            self.date_period = "ce mois"
        elif submitted_date.year == today.year:
            self.date_period = "cette année"
        else:
            self.date_period = "années précédentes"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.collaborator} - {self.emotion_type.name} ({self.date.strftime('%Y-%m-%d %H:%M')})"

    class Meta:
        verbose_name = "Emotion"
        verbose_name_plural = "Emotions"
        ordering = ["-date"]




