from django.db import models
from django.db.models import Sum, Avg, Count, F
from django.contrib.auth.models import AbstractUser, Group, Permission, AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta
import pytz
from calendar import monthrange


# +3h for timezone in Madagascar
def default_date_plus_3h():
    return timezone.now() + timedelta(hours=3)


def get_emotion_label_from_degree(degree):
    if degree is None:
        return "neutral"
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

    @property
    def emotion_summary(self):
        today = timezone.localdate()
        week_number = today.isocalendar()[1]
        month = today.month
        year = today.year

        entities = self.entities.all()
        departments = Department.objects.filter(entity__in=entities)
        services = Service.objects.filter(department__in=departments)
        collaborators = Collaborator.objects.filter(service__in=services)
        emotions = Emotion.objects.filter(collaborator__in=collaborators)

        now_today = emotions.filter(date__date=today)
        now_week = emotions.filter(week_number=week_number, year=year)
        now_month = emotions.filter(month=month, year=year)

        def avg_degree(qs):
            return qs.aggregate(avg=Avg('emotion_degree'))['avg']

        def get_summary(qs):
            degree = avg_degree(qs)
            label = get_emotion_label_from_degree(degree)
            return {'average_degree': degree, 'emotion': label}

        return {
            'today': get_summary(now_today),
            'week': get_summary(now_week),
            'month': get_summary(now_month),
        }


class Entity(models.Model):
    """Deuxième niveau (ex: Filiale, Société, Site)"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    cluster = models.ForeignKey(Cluster, on_delete=models.SET_NULL, related_name='entities', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def emotion_summary(self):
        today = timezone.localdate()
        week_number = today.isocalendar()[1]
        month = today.month
        year = today.year

        departments = self.departments.all()
        services = Service.objects.filter(department__in=departments)
        collaborators = Collaborator.objects.filter(service__in=services)
        emotions = Emotion.objects.filter(collaborator__in=collaborators)

        now_today = emotions.filter(date__date=today)
        now_week = emotions.filter(week_number=week_number, year=year)
        now_month = emotions.filter(month=month, year=year)

        def avg_degree(qs):
            return qs.aggregate(avg=Avg('emotion_degree'))['avg']

        def get_summary(qs):
            degree = avg_degree(qs)
            label = get_emotion_label_from_degree(degree)
            return {'average_degree': degree, 'emotion': label}

        return {
            'today': get_summary(now_today),
            'week': get_summary(now_week),
            'month': get_summary(now_month),
        }


class Department(models.Model):
    """Troisième niveau (ex: Département, Direction, Business Unit)"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    entity = models.ForeignKey(Entity, on_delete=models.SET_NULL, related_name='departments', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('name', 'entity')

    def __str__(self):
        return f"{self.name}"

    @property
    def emotion_summary(self):
        today = timezone.localdate()
        week_number = today.isocalendar()[1]
        month = today.month
        year = today.year

        services = self.services.all()
        collaborators = Collaborator.objects.filter(service__in=services)
        emotions = Emotion.objects.filter(collaborator__in=collaborators)

        now_today = emotions.filter(date__date=today)
        now_week = emotions.filter(week_number=week_number, year=year)
        now_month = emotions.filter(month=month, year=year)

        def avg_degree(qs):
            return qs.aggregate(avg=Avg('emotion_degree'))['avg']

        def get_summary(qs):
            degree = avg_degree(qs)
            label = get_emotion_label_from_degree(degree)
            return {'average_degree': degree, 'emotion': label}

        return {
            'today': get_summary(now_today),
            'week': get_summary(now_week),
            'month': get_summary(now_month),
        }




class Service(models.Model):
    """Quatrième niveau (ex: Service, Équipe, Cellule)"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    # SET_NULL allow null departments
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, related_name='services', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('name', 'department')

    def __str__(self):
        if self.department:
            return f"{self.name}"
        return self.name

    @property
    def emotion_summary(self):
        today = timezone.localdate()
        week_number = today.isocalendar()[1]
        month = today.month
        year = today.year

        collaborators = self.collaborators.all()
        emotions = Emotion.objects.filter(collaborator__in=collaborators)

        now_today = emotions.filter(date__date=today)
        now_week = emotions.filter(week_number=week_number, year=year)
        now_month = emotions.filter(month=month,year=year)

        def avg_degree(qs):
            return qs.aggregate(avg=Avg('emotion_degree'))['avg']

        def get_summary(qs):
            degree = avg_degree(qs)
            label = get_emotion_label_from_degree(degree)
            return {'average_degree': degree, 'emotion': label}

        return {
            'today': get_summary(now_today),
            'week': get_summary(now_week),
            'month': get_summary(now_month),
        }


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
        extra_fields.setdefault('role', 'admin')  # createsuperuseradmin

        if 'service' not in extra_fields:
            from .models import Service
            default_service, _ = Service.objects.get_or_create(
                name='Admin Service',
                department=None # might adjust Department
            )
            extra_fields['service'] = default_service
        return self.create_user(email_address, first_name, last_name, password, **extra_fields)


class Collaborator(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('employee', 'Employé'),
        ('manager', 'Manager'),
        ('department_director', 'Directeur / Chef de département'),
        ('entity_director', "Directeur d' entité"),
        ('pole_director', 'Directeur de Pôle'),
        ('admin', 'Administrateur')  # Pour les superutilisateur
    ]

    id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email_address = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    service = models.ForeignKey('Service', on_delete=models.SET_NULL, related_name="collaborators", null=True, blank=True)

    #test for hierarchy
    cluster = models.ForeignKey(Cluster, null=True, blank=True, on_delete=models.SET_NULL, related_name='collaborators')
    entity = models.ForeignKey(Entity, null=True, blank=True, on_delete=models.SET_NULL, related_name='collaborators')
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, related_name='collaborators')


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

    # For validating migrations for User
    USERNAME_FIELD = 'email_address'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = CollaboratorManager()

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.role})"

    def clean(self):

        if not self.role and (self.cluster or self.entity or self.department or self.service):
            raise ValidationError({
                "role": "veuillez indiquez le rôle s'il vous plaît"
            })

        if self.role and self.role != 'admin':
            if self.role == 'pole_director':
                if not self.cluster or self.service or self.department or self.entity:
                    raise ValidationError({
                        "role": "Seul un cluster peut/doit être attribué à l'hiérarchie d'un directeur de pôle"
                    })
                existing_pole_director = Collaborator.objects.filter(cluster=self.cluster, role='pole_director').exclude(id=self.id).first()
                if existing_pole_director:
                    raise ValidationError({
                        'cluster': f'le cluster {self.cluster.name} est déja attribué à {existing_pole_director.first_name} {existing_pole_director.last_name}'
                    })
                if self.manager:
                    raise ValidationError({
                        'manager': "Un directeur de pole ne doit plus avoir de supérieure"
                    })

            elif self.role == 'entity_director':
                if self.entity is None:
                    raise ValidationError({
                        "role": "Veuillez  attribuer juste une entité pour ce directeur"
                    })
                if self.service or self.department:
                    raise ValidationError({
                        "entity": "Aucun departement/service ne doit plus être attribué à un directeur d'entité"
                    })
                existing_entity_director = Collaborator.objects.filter(entity=self.entity, role='entity_director').exclude(id=self.id).first()
                if existing_entity_director:
                    raise ValidationError({
                       "entity": f"l'entité {self.entity.name} est déja attribué à {existing_entity_director.first_name} {existing_entity_director.last_name}"
                    })
                self.cluster = self.entity.cluster
                if self.manager:
                    if self.manager.role == self.role or self.manager.role != 'pole_director':
                        raise ValidationError({
                            "manager": "Le supérieur d'un directeur d'entité doit être uniquement un directeur de pôle"
                        })
                    if self.manager.cluster != self.cluster:
                        raise ValidationError({
                            "manager": "Le directeur d'entité n'est pas dans le même pôle que son supérieur"
                        })


            elif self.role == 'department_director':
                if self.department is None:
                    raise ValidationError({
                        "role": "veuillez attribuer juste un département pour ce chef"
                    })
                if self.service:
                    raise ValidationError({
                        "department": "Aucun service ne doit plus être attribué à un chef de département"
                    })
                existing_department_director = Collaborator.objects.filter(department=self.department, role='department_director').exclude(id=self.id).first()
                if existing_department_director:
                    raise ValidationError({
                        "department": f"le département {self.department} est déja attribué à {existing_department_director.first_name} {existing_department_director.last_name}"
                    })
                self.entity = self.department.entity
                self.cluster = self.department.entity.cluster
                if self.manager:
                    if self.manager.role == self.role or self.manager.role != 'entity_director':
                        raise ValidationError({
                            "manager": "Le supérieur d'un chef de département doit être uniquement un directeur d'entité"
                        })
                    if self.entity != self.manager.entity or self.cluster != self.manager.cluster:
                        raise ValidationError({
                            "manager": "Le chef de département n'est pas dans le même entité/cluster que son supérieur"
                        })

            else:
                if self.service is None:
                    raise ValidationError({
                        "role": "Veuillez attribuer juste un service pour ce collaborateur"
                    })
                if self.role == 'manager':
                    existing_manager = Collaborator.objects.filter(service=self.service, role='manager').exclude(id=self.id).first()
                    if existing_manager:
                        raise ValidationError({
                            "service": f"Le service {self.service} est déja attribué à {existing_manager.first_name} {existing_manager.last_name}"
                        })
                    self.department = self.service.department
                    self.entity = self.service.department.entity
                    self.cluster = self.service.department.entity.cluster
                    if self.manager:
                        if self.manager.role == self.role or self.manager.role != 'department_director':
                            raise ValidationError({
                                "manager": "Le supérieur d'un Manager doit être uniquement un chef de département"
                            })
                        if self.department != self.manager.department or self.entity != self.manager.entity or self.cluster != self.manager.cluster:
                            raise ValidationError({
                                "manager": "Le Manager n'est pas dans le même département/entité/cluster que son supérieur"
                            })
                else:
                    self.department = self.service.department
                    self.entity = self.service.department.entity
                    self.cluster = self.service.department.entity.cluster

                    if self.manager:
                        if self.manager.role == self.role or self.manager.role != 'manager':
                            raise ValidationError({
                                "manager": "Le supérieur d'un employé doit être uniquement un manager"
                            })
                        if self.service != self.manager.service or self.department != self.manager.department or self.entity != self.manager.entity or self.cluster != self.manager.cluster:
                            raise ValidationError({
                                "manager": "L'empployé nest pas dans le même service/département/entité/cluster que son Manager"
                            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def emotion_today_morning(self):
        today = timezone.localdate()
        return self.emotions.filter(
            date__date=today,
            half_day='morning'
        ).order_by('-date').first()

    @property
    def emotion_today_evening(self):
        today = timezone.localdate()
        return self.emotions.filter(
            date__date=today,
            half_day='evening'
        ).order_by('-date').first()

    @property
    def emotion_today(self):
        today = timezone.localdate()
        return self.emotions.filter(date__date=today).order_by('half_day')

    @property
    def emotion_degree_this_week(self):
        today = timezone.localdate()
        week_number = today.isocalendar()[1]
        year = today.year
        emotions = self.emotions.filter(
            week_number=week_number,
            year=year
        )
        return sum(e.emotion_degree for e in emotions)

    @property
    def emotion_this_week(self):
        degree = self.emotion_degree_this_week
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

    @property
    def emotion_degree_this_month(self):
        today = timezone.localdate()
        month = today.month
        year = today.year
        emotions = self.emotions.filter(
            month = month,
            year = year
        )
        return sum(e.emotion_degree for e in emotions)

    @property
    def emotion_this_month(self):
        degree = self.emotion_degree_this_month
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

class Emotion(models.Model):
    HALF_DAY_CHOICES = [
        ('morning', 'Morning'),
        ('evening', 'Evening'),
    ]

    id = models.AutoField(primary_key=True)
    emotion_type = models.ForeignKey('EmotionType', on_delete=models.CASCADE, related_name="emotions")
    emotion_degree = models.IntegerField(editable=False)
    collaborator = models.ForeignKey('Collaborator', on_delete=models.CASCADE, related_name="emotions")
    date = models.DateTimeField(default=default_date_plus_3h)  # à revoir
    week_number = models.PositiveIntegerField(editable=False)
    month = models.PositiveIntegerField(editable=False)
    year = models.PositiveIntegerField(editable=False)
    half_day = models.CharField(max_length=10, choices=HALF_DAY_CHOICES, editable=False)
    _date_period = models.CharField(max_length=20, editable=False) # should be a hidden field

    @property
    def date_period(self):
        """
        Dynamically calculate the date period based on the current date
        """
        today = timezone.localdate()
        submitted_date = self.date.date()

        if submitted_date == today:
            return 'ce jour'
        elif submitted_date.isocalendar()[1] == today.isocalendar()[1] and submitted_date.year == today.year:
            return 'cette semaine'
        elif submitted_date.month == today.month and submitted_date.year == today.year:
            return 'ce mois'
        elif submitted_date.year == today.year:
            return 'cette année'
        else:
            return "années précédentes"

    def save(self, *args, **kwargs):
        # Set degree from emotion_type
        if self.emotion_type:
            self.emotion_degree = self.emotion_type.degree

        # set date_related fields
        dt = self.date if self.date else timezone.now() + timedelta(hours=3) # +3h in Madagascar zone
        self.week_number = dt.isocalendar()[1]
        self.month = dt.month
        self.year = dt.year

        # set half_day
        self.half_day = "morning" if dt.hour < 12 else "evening"

        # Store the calculated date_period in the hidden field if needed
        self._date_period = self.date_period

        super().save(*args, **kwargs)

    def __str__(self):
        return (f"{self.collaborator} - {self.emotion_type.name} ({self.date.strftime('%Y-%m-%d %H:%M')}) - "
                f"degré : {self.emotion_degree} - période dans la journée : {self.half_day} - période : {self.date_period}")


    class Meta:
        verbose_name = "Emotion"
        verbose_name_plural = "Emotions"
        ordering = ["-date"]





