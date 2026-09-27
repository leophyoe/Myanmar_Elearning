try:
    from rest_framework import serializers
    from .models import (
        LabCategory, Lab, LabObjective, LabHint, LabAttachment,
        LabInstance, LabSubmission, ChallengeCategory, Challenge,
        ChallengeSubmission, CTFEvent, CTFScore
    )

    class LabCategorySerializer(serializers.ModelSerializer):
        class Meta:
            model = LabCategory
            fields = ['id', 'name', 'slug', 'description', 'icon']

    class LabObjectiveSerializer(serializers.ModelSerializer):
        class Meta:
            model = LabObjective
            fields = ['id', 'title', 'description', 'order', 'points', 'required']

    class LabHintSerializer(serializers.ModelSerializer):
        class Meta:
            model = LabHint
            fields = ['id', 'order', 'hint_text', 'penalty_percent']

    class LabListSerializer(serializers.ModelSerializer):
        category = LabCategorySerializer(read_only=True)

        class Meta:
            model = Lab
            fields = [
                'id', 'uuid', 'name', 'slug', 'short_description', 'category',
                'difficulty', 'type', 'estimated_minutes', 'points',
                'access_type', 'terminal_enabled', 'web_access_enabled', 'is_published'
            ]

    class LabDetailSerializer(serializers.ModelSerializer):
        category = LabCategorySerializer(read_only=True)
        objectives = LabObjectiveSerializer(many=True, read_only=True)
        hints = LabHintSerializer(many=True, read_only=True)

        class Meta:
            model = Lab
            fields = [
                'id', 'uuid', 'name', 'slug', 'short_description', 'description',
                'category', 'difficulty', 'type', 'estimated_minutes', 'points',
                'access_type', 'terminal_enabled', 'web_access_enabled',
                'max_runtime_minutes', 'objectives', 'hints', 'is_published'
            ]
            # Flags are strictly excluded to enforce zero-trust answer secrecy

    class LabInstanceSerializer(serializers.ModelSerializer):
        lab_name = serializers.CharField(source='lab.name', read_only=True)
        lab_slug = serializers.CharField(source='lab.slug', read_only=True)

        class Meta:
            model = LabInstance
            fields = [
                'id', 'uuid', 'lab', 'lab_name', 'lab_slug', 'status',
                'internal_address', 'access_url', 'started_at', 'expires_at',
                'stopped_at', 'last_activity'
            ]
            read_only_fields = ['uuid', 'status', 'internal_address', 'access_url', 'started_at', 'expires_at', 'stopped_at']

    class LabSubmissionSerializer(serializers.ModelSerializer):
        class Meta:
            model = LabSubmission
            fields = ['id', 'lab', 'flag_submitted', 'is_correct', 'points_awarded', 'submitted_at']
            read_only_fields = ['is_correct', 'points_awarded', 'submitted_at']

    class ChallengeCategorySerializer(serializers.ModelSerializer):
        class Meta:
            model = ChallengeCategory
            fields = ['id', 'name', 'slug', 'description', 'icon']

    class ChallengeListSerializer(serializers.ModelSerializer):
        category = ChallengeCategorySerializer(read_only=True)

        class Meta:
            model = Challenge
            fields = ['id', 'title', 'slug', 'category', 'difficulty', 'points', 'solves_count', 'is_active']

    class ChallengeDetailSerializer(serializers.ModelSerializer):
        category = ChallengeCategorySerializer(read_only=True)

        class Meta:
            model = Challenge
            fields = ['id', 'title', 'slug', 'category', 'difficulty', 'points', 'description', 'instructions', 'solves_count', 'is_active']
            # Flag is strictly excluded to prevent answer leakage

    class ChallengeSubmissionSerializer(serializers.ModelSerializer):
        class Meta:
            model = ChallengeSubmission
            fields = ['id', 'challenge', 'flag_submitted', 'is_correct', 'points_awarded', 'submitted_at']
            read_only_fields = ['is_correct', 'points_awarded', 'submitted_at']

    class CTFEventSerializer(serializers.ModelSerializer):
        is_live = serializers.BooleanField(read_only=True)

        class Meta:
            model = CTFEvent
            fields = ['id', 'name', 'slug', 'description', 'start_time', 'end_time', 'status', 'max_participants', 'is_live']

    class CTFScoreSerializer(serializers.ModelSerializer):
        student_username = serializers.CharField(source='student.username', read_only=True)
        student_name = serializers.CharField(source='student.get_full_name', read_only=True)

        class Meta:
            model = CTFScore
            fields = ['student_username', 'student_name', 'points', 'lab_points', 'challenge_points', 'solves_count', 'labs_completed_count']

except ImportError:
    pass

