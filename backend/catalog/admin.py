from django.contrib import admin

from .models import CarModel, Generation, Make, Modification


@admin.register(Make)
class MakeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "country", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(CarModel)
class CarModelAdmin(admin.ModelAdmin):
    list_display = ("id", "make", "name", "slug", "created_at")
    list_filter = ("make",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Generation)
class GenerationAdmin(admin.ModelAdmin):
    list_display = ("id", "car_model", "make", "name", "body_style", "production_start", "production_end", "region")
    list_filter = ("make", "body_style", "region")
    search_fields = ("name", "chassis_codes")


@admin.register(Modification)
class ModificationAdmin(admin.ModelAdmin):
    list_display = ("id", "generation", "code", "variant_name", "engine_code", "fuel_type", "transmission_type", "power_hp")
    list_filter = ("fuel_type", "transmission_type", "drive_type")
    search_fields = ("code", "variant_name", "engine_code")
