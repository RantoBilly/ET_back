from rest_framework import serializers
from .models import Emotion, Collaborator, Service, Team, Company, Cluster

class EmotionSerializer(serializers.ModelSerializer):
    relative_period = serializers.CharField(read_only=True)
    formatted_date = serializers.CharField(read_only=True)
    submission_period = serializers.CharField(read_only=True)
    emotion_status = serializers.CharField(read_only=True)

    class Meta:
        model = Emotion
        fields = [
            'id',
            'collaborator',
            'emotion_type',
            'emotion_degree',
            'emotion_status',
            'date',
            'submission_time',
            'period',
            'submission_period',
            'comment',
            'team',
            'company',
            'cluster',
            'relative_period',
            'formatted_date'
        ]
        read_only_fields = ('period', 'submission_time', 'emotion_degree')


class CollaboratorSerializer(serializers.ModelSerializer):
    today_morning_emotion_status = serializers.CharField(read_only=True)
    has_submitted_morning_emotion = serializers.BooleanField(read_only=True)
    today_morning_emotion = serializers.SerializerMethodField()
    weekly_emotion_summary = serializers.SerializerMethodField()
    emotion_trend = serializers.SerializerMethodField()
    emotion_trends = serializers.SerializerMethodField()


    class Meta:
        model = Collaborator
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'role',
            'team',
            'company',
            'cluster',
            'manager',
            'today_morning_emotion',
            'today_morning_emotion_status',
            'has_submitted_morning_emotion',
            'weekly_emotion_summary',
            'emotion_trend',
            'weekly_summary',
            'monthly_summary',
            'emotion_trends'
        ]
        read_only_fields = (
            'today_morning_emotion',
            'today_morning_emotion_status',
            'has_submitted_morning_emotion',
            'weekly_emotion_summary',
            'emotion_trend',
            'weekly_summary',
            'monthly_summary',
            'emotion_trends'
        )

    def get_today_morning_emotion(self, obj):
        emotion = obj.today_morning_emotion
        if emotion:
            return {
                'type': emotion.emotion_type.name,
                'degree': emotion.emotion_degree,
                'status': emotion.emotion_status,
                'comment': emotion.comment
            }
        return None

    def get_weekly_emotion_summary(self, obj):
        return obj.weekly_emotion_summary

    def get_emotion_trend(self, obj):
        return obj.get_emotion_trend()

    def get_emotion_trends(self, obj):
        return obj.emotion_trends

    def get_weekly_summary(self, obj):
        return obj.weekly_emotion_status

    def get_monthly_summary(self, obj):
        return obj.monthly_emotion_status


class ServiceEmotionSerializer(serializers.ModelSerializer):
    emotions_average = serializers.SerializerMethodField()
    emotions_summary = serializers.CharField(read_only=True)

    class Meta:
        model = Service
        fields = [
            'id',
            'name',
            'team',
            'emotions_average',
            'emotions_summary'
        ]

    def get_emotions_average(self, obj):
        averages = obj.get_emotions_average()
        for period in averages.values():
            if 'average' in period:
                period['status'] = obj.get_emotion_status(period['average'])
        return averages


class TeamEmotionSerializer(serializers.ModelSerializer):
    emotions_average = serializers.SerializerMethodField()
    emotions_summary = serializers.CharField(read_only=True)

    class Meta:
        model = Team
        fields = [
            'id',
            'name',
            'company',
            'emotions_average',
            'emotions_summary'
        ]

    def get_emotions_average(self, obj):
        averages = obj.get_emotions_average()
        for period in ['daily', 'weekly', 'monthly']:
            if period in averages and 'average' in averages[period]:
                averages[period]['status'] = obj.get_emotion_status(
                    averages[period]['average']
                )
        return averages


class CompanyEmotionSerializer(serializers.ModelSerializer):
    emotions_average = serializers.SerializerMethodField()
    emotions_summary = serializers.CharField(read_only=True)

    class Meta:
        model = Company
        fields = [
            'id',
            'name',
            'emotions_average',
            'emotions_summary'
        ]

    def get_emotions_average(self, obj):
        averages = obj.get_emotions_average()
        for period in ['daily', 'weekly', 'monthly']:
            if period in averages and 'average' in averages[period]:
                averages[period]['status'] = obj.get_emotion_status(
                    averages[period]['average']
                )
        return averages


class ClusterEmotionSerializer(serializers.ModelSerializer):
    emotions_average = serializers.SerializerMethodField()
    emotions_summary = serializers.CharField(read_only=True)

    class Meta:
        model = Cluster
        fields = [
            'id',
            'name',
            'emotions_average',
            'emotions_summary'
        ]

    def get_emotions_average(self, obj):
        averages = obj.get_emotions_average()
        for period in ['daily', 'weekly', 'monthly']:
            if period in averages and 'average' in averages[period]:
                averages[period]['status'] = obj.get_emotion_status(
                    averages[period]['average']
                )
        return averages