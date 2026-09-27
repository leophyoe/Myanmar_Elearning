try:
    from rest_framework import viewsets, permissions, filters
    from .models import (
        LabCategory, Lab, LabInstance, LabSubmission,
        ChallengeCategory, Challenge, ChallengeSubmission,
        CTFEvent, CTFScore
    )
    from .serializers import (
        LabCategorySerializer, LabListSerializer, LabDetailSerializer,
        LabInstanceSerializer, LabSubmissionSerializer,
        ChallengeCategorySerializer, ChallengeListSerializer, ChallengeDetailSerializer,
        ChallengeSubmissionSerializer, CTFEventSerializer, CTFScoreSerializer
    )
    from .permissions import IsStudentOrStaff, IsLabOwnerOrStaff


    class LabCategoryViewSet(viewsets.ReadOnlyModelViewSet):
        queryset = LabCategory.objects.all()
        serializer_class = LabCategorySerializer
        permission_classes = [permissions.AllowAny]


    class LabViewSet(viewsets.ReadOnlyModelViewSet):
        lookup_field = 'slug'
        permission_classes = [permissions.AllowAny]

        def get_queryset(self):
            user = self.request.user
            if user.is_authenticated and (user.is_instructor or user.is_staff):
                return Lab.objects.all().select_related('category', 'created_by')
            return Lab.objects.filter(is_published=True).select_related('category', 'created_by')

        def get_serializer_class(self):
            if self.action == 'retrieve':
                return LabDetailSerializer
            return LabListSerializer


    class LabInstanceViewSet(viewsets.ModelViewSet):
        serializer_class = LabInstanceSerializer
        permission_classes = [IsStudentOrStaff, IsLabOwnerOrStaff]

        def get_queryset(self):
            user = self.request.user
            if user.is_instructor or user.is_staff:
                return LabInstance.objects.all().select_related('lab', 'student')
            return LabInstance.objects.filter(student=user).select_related('lab', 'student')


    class ChallengeViewSet(viewsets.ReadOnlyModelViewSet):
        lookup_field = 'slug'
        queryset = Challenge.objects.filter(is_active=True).select_related('category')
        permission_classes = [permissions.AllowAny]

        def get_serializer_class(self):
            if self.action == 'retrieve':
                return ChallengeDetailSerializer
            return ChallengeListSerializer


    class CTFEventViewSet(viewsets.ReadOnlyModelViewSet):
        queryset = CTFEvent.objects.all()
        serializer_class = CTFEventSerializer
        permission_classes = [permissions.AllowAny]


    class CTFScoreViewSet(viewsets.ReadOnlyModelViewSet):
        queryset = CTFScore.objects.select_related('student').order_by('-points')
        serializer_class = CTFScoreSerializer
        permission_classes = [permissions.AllowAny]

except ImportError:
    pass

