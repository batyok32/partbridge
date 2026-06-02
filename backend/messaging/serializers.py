from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from .models import Message, Quote, Thread

User = get_user_model()


class ThreadCounterpartySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "name", "email")


class MessageSerializer(serializers.ModelSerializer):
    sender = ThreadCounterpartySerializer(read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ("id", "sender", "body", "image_url", "is_system", "created_at")

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        try:
            url = obj.image.url
            return request.build_absolute_uri(url) if request else url
        except Exception:
            return None


class QuoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quote
        fields = ("id", "price", "note", "status", "created_at", "updated_at")
        read_only_fields = ("id", "status", "created_at", "updated_at")

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quote price must be greater than zero.")
        return value


class ThreadSerializer(serializers.ModelSerializer):
    buyer_id = serializers.IntegerField(read_only=True)
    seller_id = serializers.IntegerField(read_only=True)
    counterparty = serializers.SerializerMethodField()
    vehicle_part_id = serializers.IntegerField(source="vehicle_part.id", read_only=True)
    vehicle_id = serializers.IntegerField(source="vehicle_part.vehicle_id", read_only=True)
    vehicle_part_label = serializers.CharField(source="vehicle_part.label", read_only=True)
    unread_count = serializers.SerializerMethodField()
    latest_quote = serializers.SerializerMethodField()

    class Meta:
        model = Thread
        fields = (
            "id",
            "status",
            "subject",
            "buyer_id",
            "seller_id",
            "vehicle_part_id",
            "vehicle_id",
            "vehicle_part_label",
            "counterparty",
            "last_message_preview",
            "last_message_at",
            "unread_count",
            "latest_quote",
            "created_at",
            "updated_at",
        )

    def get_counterparty(self, obj):
        u = self.context["request"].user
        other = obj.seller if u.id == obj.buyer_id else obj.buyer
        return ThreadCounterpartySerializer(other).data

    def get_unread_count(self, obj):
        u = self.context["request"].user
        last_read = obj.buyer_last_read_at if u.id == obj.buyer_id else obj.seller_last_read_at
        q = obj.messages.all()
        if last_read is not None:
            q = q.filter(created_at__gt=last_read)
        q = q.exclude(sender_id=u.id)
        return q.count()

    def get_latest_quote(self, obj):
        q = obj.quotes.order_by("-created_at").first()
        if not q:
            return None
        return QuoteSerializer(q).data


class ThreadDetailSerializer(ThreadSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    quotes = QuoteSerializer(many=True, read_only=True)

    class Meta(ThreadSerializer.Meta):
        fields = ThreadSerializer.Meta.fields + ("messages", "quotes")


class StartThreadSerializer(serializers.Serializer):
    vehicle_part_id = serializers.IntegerField()
    message = serializers.CharField(required=False, allow_blank=True, max_length=4000)


class BulkRfqSerializer(serializers.Serializer):
    vehicle_part_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=100)
    message = serializers.CharField(max_length=4000)


class SendMessageSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=4000, required=False, allow_blank=True)
    image = serializers.ImageField(required=False)

    def validate(self, data):
        if not data.get("body") and not data.get("image"):
            raise serializers.ValidationError("Either body or image is required.")
        return data


class MarkReadSerializer(serializers.Serializer):
    marked_at = serializers.DateTimeField(required=False)

    def validate_marked_at(self, value):
        return value or timezone.now()


def thread_for_user_qs(user):
    return Thread.objects.filter(Q(buyer=user) | Q(seller=user)).select_related(
        "buyer", "seller", "vehicle_part"
    )
