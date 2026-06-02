from django.contrib import admin

from .models import Message, Thread


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "buyer", "seller", "item", "last_message_at", "created_at")
    search_fields = ("buyer__email", "seller__email")
    readonly_fields = ("created_at",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "sender", "is_read", "sent_at")
    list_filter = ("is_read",)
    search_fields = ("sender__email", "body")
    readonly_fields = ("sent_at",)
