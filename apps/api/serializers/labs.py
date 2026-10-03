from rest_framework import serializers
from apps.labs.models import Lab, LabInstance


class LabListSerializer(serializers.ModelSerializer):
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)
    lab_type_display = serializers.CharField(source='get_lab_type_display', read_only=True)

    class Meta:
        model = Lab
        fields = [
            'id', 'title', 'slug', 'difficulty', 'difficulty_display',
            'lab_type', 'lab_type_display', 'points', 'estimated_minutes'
        ]


class LabDetailSerializer(LabListSerializer):
    class Meta(LabListSerializer.Meta):
        fields = LabListSerializer.Meta.fields + [
            'description', 'learning_objectives', 'prerequisites', 'tasks'
        ]


class LabInstanceSerializer(serializers.ModelSerializer):
    lab_slug = serializers.CharField(source='lab.slug', read_only=True)
    lab_title = serializers.CharField(source='lab.title', read_only=True)
    remaining_seconds = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = LabInstance
        fields = [
            'id', 'lab_slug', 'lab_title', 'status', 'status_display',
            'target_ip', 'started_at', 'expires_at', 'remaining_seconds',
            'extensions_used', 'created_at'
        ]

    def get_remaining_seconds(self, obj):
        return obj.remaining_seconds()
