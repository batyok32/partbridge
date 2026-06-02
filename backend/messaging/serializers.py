from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Message, Thread

User = get_user_model()


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ("id", "thread", "sender", "body", "is_read", "sent_at")
        read_only_fields = ("id", "thread", "sender", "sent_at")


class ThreadSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Thread
        fields = ("id", "buyer", "seller", "item", "created_at", "last_message_at", "last_message", "unread_count")
        read_only_fields = ("id", "buyer", "created_at", "last_message_at")

    def get_last_message(self, obj):
        msg = obj.messages.last()
        if not msg:
            return None
        return {"id": msg.id, "body": msg.body[:120], "sent_at": msg.sent_at}

    def get_unread_count(self, obj):
        user = self.context.get("request") and self.context["request"].user
        if not user:
            return 0
        return obj.messages.filter(is_read=False).exclude(sender=user).count()


class StartThreadSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    body = serializers.CharField()
