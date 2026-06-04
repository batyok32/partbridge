from django.db.models import Count, Q
from rest_framework import generics
from rest_framework.permissions import AllowAny

from parts.models import Item

from .models import CarModel, Generation, Make, Modification
from .serializers import CarModelSerializer, GenerationSerializer, MakeSerializer, ModificationSerializer


class MakeListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = MakeSerializer

    def get_queryset(self):
        qs = Make.objects.all()
        if self.request.query_params.get("with_counts") in ("1", "true", "yes"):
            qs = qs.annotate(
                listing_count=Count(
                    "generations__vehicles__items",
                    filter=Q(generations__vehicles__items__status=Item.Status.ACTIVE),
                    distinct=True,
                )
            ).order_by("-listing_count", "name")
        else:
            qs = qs.order_by("name")
        return qs


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
