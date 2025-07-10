from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import EmotionType, Collaborator, Emotion, Service, Team, Company, Cluster

@admin.register(EmotionType)
class EmotionTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'emoticon', 'degree')
    readonly_fields = ('degree',)  # Le degré ne peut pas être modifié manuellement
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Collaborator)
class CollaboratorAdmin(UserAdmin):
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'role',
        'team',
        'today_morning_emotion_status',
        'has_submitted_morning_emotion',
        'get_weekly_emotion_summary',
        'get_emotion_trend',
        'get_weekly_emotion_type',
        'get_weekly_summary',
        'get_monthly_summary'
    )
    list_filter = (
        'role',
        'team',
        'company',
        'cluster',
        'is_active'
    )
    search_fields = (
        'username',
        'first_name',
        'last_name',
        'email'
    )
    ordering = ('username',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informations personnelles', {'fields': ('first_name', 'last_name', 'email')}),
        ('Rôle et organisation', {'fields': ('role', 'team', 'company', 'cluster', 'manager')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role', 'team', 'company', 'cluster', 'manager'),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        return readonly_fields + ('today_morning_emotion_status', 'has_submitted_morning_emotion')

    def get_weekly_emotion_summary(self, obj):
        summary = obj.weekly_emotion_summary
        return (
            f"Auj: {summary['today_sum']} | "
            f"Sem: {summary['rest_of_week_sum']} | "
            f"Total: {summary['total_sum']}"
        )

    get_weekly_emotion_summary.short_description = "Émotions de la semaine"

    def get_weekly_emotion_type(self, obj):
        emotion = obj.weekly_emotion_summary['weekly_emotion']
        return f"{emotion['type']} ({emotion['description']})"

    get_weekly_emotion_type.short_description = "Bilan hebdomadaire"

    def get_emotion_trend(self, obj):
        return obj.get_emotion_trend()

    get_emotion_trend.short_description = "Tendance"

    def get_weekly_summary(self, obj):
        summary = obj.weekly_emotion_summary
        emotion = summary['weekly_emotion']
        return f"Sem: {summary['total_sum']} ({emotion['type']})"

    get_weekly_summary.short_description = "Bilan semaine"

    def get_monthly_summary(self, obj):
        summary = obj.monthly_emotion_summary
        emotion = summary['monthly_emotion']
        return f"Mois: {summary['total_sum']} ({emotion['type']})"

    get_monthly_summary.short_description = "Bilan mois"


@admin.register(Emotion)
class EmotionAdmin(admin.ModelAdmin):
    list_display = (
        'collaborator',
        'emotion_type',
        'emotion_degree',
        'emotion_status',
        'formatted_date',
        'submission_period',
        'submission_time',
        'team'
    )
    list_filter = (
        'date',
        'period',
        'emotion_type',
        'emotion_degree',
        'team',
        'company',
        'cluster'
    )
    search_fields = (
        'collaborator__username',
        'collaborator__first_name',
        'collaborator__last_name',
        'comment'
    )
    readonly_fields = ('period', 'submission_time', 'emotion_degree')
    date_hierarchy = 'date'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'collaborator',
            'emotion_type',
            'team',
            'company',
            'cluster'
        )

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'team',
        'get_daily_average',
        'get_weekly_average',
        'get_monthly_average'
    )
    list_filter = ('team', 'company', 'cluster')
    search_fields = ('name', 'description')

    def get_daily_average(self, obj):
        averages = obj.get_emotions_average()
        avg = averages['daily']['average']
        status = obj.get_emotion_status(avg)
        return f"{avg} ({status['status']})"
    get_daily_average.short_description = "Moyenne du jour"

    def get_weekly_average(self, obj):
        averages = obj.get_emotions_average()
        avg = averages['weekly']['average']
        status = obj.get_emotion_status(avg)
        return f"{avg} ({status['status']})"
    get_weekly_average.short_description = "Moyenne de la semaine"

    def get_monthly_average(self, obj):
        averages = obj.get_emotions_average()
        avg = averages['monthly']['average']
        status = obj.get_emotion_status(avg)
        return f"{avg} ({status['status']})"
    get_monthly_average.short_description = "Moyenne du mois"


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'company',
        'get_daily_average',
        'get_weekly_average',
        'get_monthly_average',
        'get_team_size'
    )
    list_filter = ('company', 'cluster')
    search_fields = ('name', 'description')

    def get_daily_average(self, obj):
        averages = obj.get_emotions_average()
        avg = averages['daily']['average']
        participation = averages['daily']['participation_rate']
        status = obj.get_emotion_status(avg)
        return f"{avg} ({status['status']}) - {participation}% participation"
    get_daily_average.short_description = "Moyenne du jour"

    def get_weekly_average(self, obj):
        averages = obj.get_emotions_average()
        avg = averages['weekly']['average']
        participation = averages['weekly']['participation_rate']
        status = obj.get_emotion_status(avg)
        return f"{avg} ({status['status']}) - {participation}% participation"
    get_weekly_average.short_description = "Moyenne de la semaine"

    def get_monthly_average(self, obj):
        averages = obj.get_emotions_average()
        avg = averages['monthly']['average']
        participation = averages['monthly']['participation_rate']
        status = obj.get_emotion_status(avg)
        return f"{avg} ({status['status']}) - {participation}% participation"
    get_monthly_average.short_description = "Moyenne du mois"

    def get_team_size(self, obj):
        return obj.get_emotions_average()['team_size']
    get_team_size.short_description = "Taille de l'équipe"


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'get_daily_average',
        'get_weekly_average',
        'get_monthly_average',
        'get_company_stats'
    )
    search_fields = ('name', 'description')

    def get_daily_average(self, obj):
        averages = obj.get_emotions_average()
        avg = averages['daily']['average']
        participation = averages['daily']['participation_rate']
        status = obj.get_emotion_status(avg)
        return (
            f"{avg} ({status['status']}) - "
            f"{participation}% participation"
        )
    get_daily_average.short_description = "Moyenne du jour"

    def get_weekly_average(self, obj):
        averages = obj.get_emotions_average()
        avg = averages['weekly']['average']
        participation = averages['weekly']['participation_rate']
        status = obj.get_emotion_status(avg)
        return (
            f"{avg} ({status['status']}) - "
            f"{participation}% participation"
        )
    get_weekly_average.short_description = "Moyenne de la semaine"

    def get_monthly_average(self, obj):
        averages = obj.get_emotions_average()
        avg = averages['monthly']['average']
        participation = averages['monthly']['participation_rate']
        status = obj.get_emotion_status(avg)
        return (
            f"{avg} ({status['status']}) - "
            f"{participation}% participation"
        )
    get_monthly_average.short_description = "Moyenne du mois"

    def get_company_stats(self, obj):
        stats = obj.get_emotions_average()['company_stats']
        return (
            f"{stats['teams']} équipes, "
            f"{stats['services']} services, "
            f"{stats['collaborators']} collaborateurs"
        )
    get_company_stats.short_description = "Statistiques"


@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'get_daily_average',
        'get_weekly_average',
        'get_monthly_average',
        'get_cluster_stats'
    )
    search_fields = ('name', 'description')

    def get_daily_average(self, obj):
        averages = obj.get_emotions_average()
        avg = averages['daily']['average']
        participation = averages['daily']['participation_rate']
        status = obj.get_emotion_status(avg)
        return (
            f"{avg} ({status['status']}) - "
            f"{participation}% participation"
        )
    get_daily_average.short_description = "Moyenne du jour"

    def get_weekly_average(self, obj):
        averages = obj.get_emotions_average()
        avg = averages['weekly']['average']
        participation = averages['weekly']['participation_rate']
        status = obj.get_emotion_status(avg)
        return (
            f"{avg} ({status['status']}) - "
            f"{participation}% participation"
        )
    get_weekly_average.short_description = "Moyenne de la semaine"

    def get_monthly_average(self, obj):
        averages = obj.get_emotions_average()
        avg = averages['monthly']['average']
        participation = averages['monthly']['participation_rate']
        status = obj.get_emotion_status(avg)
        return (
            f"{avg} ({status['status']}) - "
            f"{participation}% participation"
        )
    get_monthly_average.short_description = "Moyenne du mois"

    def get_cluster_stats(self, obj):
        stats = obj.get_emotions_average()['cluster_stats']
        return (
            f"{stats['companies']} entreprises, "
            f"{stats['teams']} équipes, "
            f"{stats['services']} services, "
            f"{stats['collaborators']} collaborateurs"
        )
    get_cluster_stats.short_description = "Statistiques"