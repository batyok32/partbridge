from django.contrib import admin

from .models import Message, Quote, Thread


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "buyer", "seller", "vehicle_part", "status", "last_message_at")
    list_filter = ("status",)
    search_fields = ("buyer__email", "seller__email", "vehicle_part__label")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "sender", "is_system", "created_at")
    list_filter = ("is_system",)
    search_fields = ("thread__id", "sender__email", "body")


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "seller", "price", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("thread__id", "seller__email", "note")
