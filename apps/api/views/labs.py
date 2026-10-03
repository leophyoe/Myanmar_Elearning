from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from apps.labs.models import Lab, LabInstance, InstanceStatus
from apps.api.serializers.labs import (
    LabListSerializer, LabDetailSerializer, LabInstanceSerializer
)
from apps.api.pagination import StandardResultsSetPagination


class LabListAPIView(APIView):
    """
    GET /api/v1/labs/
    Lists interactive sandbox lab exercises and technical cyber challenges.
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        qs = Lab.objects.all().order_by('difficulty', 'title')
        category = request.query_params.get('category')
        if category:
            qs = qs.filter(template__category=category)

        difficulty = request.query_params.get('difficulty')
        if difficulty:
            qs = qs.filter(difficulty=difficulty)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = LabListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class LabDetailAPIView(APIView):
    """
    GET /api/v1/labs/<slug>/
    Retrieves lab documentation, step-by-step learning objectives, and task flags.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug):
        lab = get_object_or_404(Lab, slug=slug)
        serializer = LabDetailSerializer(lab)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ActiveLabInstancesAPIView(APIView):
    """
    GET /api/v1/labs/instances/active/
    Returns active running/provisioning sandbox containers assigned to the requesting student.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = LabInstance.objects.filter(
            user=request.user,
            status__in=[InstanceStatus.RUNNING, InstanceStatus.PROVISIONING]
        ).select_related('lab')
        serializer = LabInstanceSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LabStartAPIView(APIView):
    """
    POST /api/v1/labs/<slug>/start/
    Provisions and starts an isolated hands-on lab sandbox instance.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, slug):
        lab = get_object_or_404(Lab, slug=slug)

        # Stop existing active instances for this lab if any
        LabInstance.objects.filter(
            user=request.user,
            lab=lab,
            status__in=[InstanceStatus.RUNNING, InstanceStatus.PROVISIONING]
        ).update(status=InstanceStatus.STOPPED)

        duration = getattr(lab.template, 'default_duration_minutes', 60)
        now = timezone.now()
        instance = LabInstance.objects.create(
            lab=lab,
            user=request.user,
            status=InstanceStatus.RUNNING,
            target_ip='10.10.10.15',
            started_at=now,
            expires_at=now + timedelta(minutes=duration),
        )
        instance.generate_dynamic_flag()
        instance.save()

        return Response({
            'message': 'Lab sandbox instance provisioned successfully.',
            'instance': LabInstanceSerializer(instance).data
        }, status=status.HTTP_201_CREATED)


class LabStopAPIView(APIView):
    """
    POST /api/v1/labs/instances/<id>/stop/
    Stops a running student sandbox container.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        instance = get_object_or_404(LabInstance, pk=pk, user=request.user)
        instance.status = InstanceStatus.STOPPED
        instance.save(update_fields=['status'])
        return Response({
            'message': 'Lab instance stopped.',
            'instance': LabInstanceSerializer(instance).data
        }, status=status.HTTP_200_OK)
