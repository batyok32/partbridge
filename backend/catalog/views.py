from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import CarModel, Generation, Make, Modification
from .serializers import CarModelSerializer, GenerationSerializer, MakeSerializer, ModificationSerializer


class MakeListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = MakeSerializer
    queryset = Make.objects.all()


class CarModelListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CarModelSerializer

    def get_queryset(self):
        qs = CarModel.objects.all()
        make_id = self.request.query_params.get("make_id")
        if make_id:
            qs = qs.filter(make_id=make_id)
        return qs


class GenerationListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = GenerationSerializer

    def get_queryset(self):
        qs = Generation.objects.all()
        model_id = self.request.query_params.get("model_id")
        if model_id:
            qs = qs.filter(car_model_id=model_id)
        return qs


class ModificationListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ModificationSerializer

    def get_queryset(self):
        qs = Modification.objects.all()
        generation_id = self.request.query_params.get("generation_id")
        if generation_id:
            qs = qs.filter(generation_id=generation_id)
        return qs
