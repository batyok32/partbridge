from django.conf import settings
from django.db import models
from django.utils import timezone


class Thread(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="buyer_threads",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_threads",
    )
    vehicle_part = models.ForeignKey(
        "vehicles.VehiclePart",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="message_threads",
    )
    subject = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    buyer_last_read_at = models.DateTimeField(null=True, blank=True)
    seller_last_read_at = models.DateTimeField(null=True, blank=True)
    last_message_at = models.DateTimeField(default=timezone.now)
    last_message_preview = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_message_at", "-id"]

    def __str__(self):
        part_label = self.vehicle_part.label if self.vehicle_part else "General"
        return f"Thread {self.id}: {part_label}"

    def touch_from_message(self, body: str) -> None:
        preview = (body or "").strip().replace("\n", " ")
        self.last_message_at = timezone.now()
        self.last_message_preview = preview[:240]
        self.save(update_fields=["last_message_at", "last_message_preview", "updated_at"])


class Message(models.Model):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    body = models.TextField(blank=True)
    image = models.ImageField(upload_to="message_images/%Y/%m/", null=True, blank=True)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Message {self.id} in thread {self.thread_id}"


class Quote(models.Model):
    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="quotes")
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_quotes",
    )
    vehicle_part = models.ForeignKey(
        "vehicles.VehiclePart",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotes",
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SENT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Quote {self.id} in thread {self.thread_id}"
