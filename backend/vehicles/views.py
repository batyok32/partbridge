from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Vehicle, VehiclePhoto
from .serializers import (
    VehicleCreateUpdateSerializer,
    VehicleDetailSerializer,
    VehicleListSerializer,
    VehiclePhotoSerializer,
)


class VehicleListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return VehicleCreateUpdateSerializer
        return VehicleListSerializer

    def get_queryset(self):
        return Vehicle.objects.filter(seller=self.request.user)

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)


class VehicleDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return VehicleCreateUpdateSerializer
        return VehicleDetailSerializer

    def get_queryset(self):
        return Vehicle.objects.filter(seller=self.request.user).prefetch_related("photos")


class VehiclePhotoListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, vehicle_id):
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, seller=request.user)
        photos = vehicle.photos.all()
        return Response(VehiclePhotoSerializer(photos, many=True).data)

    def post(self, request, vehicle_id):
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, seller=request.user)
        ser = VehiclePhotoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(vehicle=vehicle)
        return Response(ser.data, status=status.HTTP_201_CREATED)


class VehiclePhotoDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, vehicle_id, photo_id):
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, seller=request.user)
        photo = get_object_or_404(VehiclePhoto, pk=photo_id, vehicle=vehicle)
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
