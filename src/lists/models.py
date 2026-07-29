from django.db import models
from django.db.models import Q
from django.urls import reverse

# Create your models here.
class Item(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Open"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"

    text = models.TextField(default="")
    list = models.ForeignKey('List', default=None, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    completed_at = models.DateTimeField(blank=True, null=True)
    archived_at = models.DateTimeField(blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    position = models.PositiveIntegerField(default=0)
    tags = models.ManyToManyField('Tag', blank=True, related_name='items')

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("list", "text"),
                condition=~Q(status="archived"),
                name="unique_active_list_item",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="active",
                        completed_at__isnull=True,
                        archived_at__isnull=True,
                    )
                    | Q(
                        status="completed",
                        completed_at__isnull=False,
                        archived_at__isnull=True,
                    )
                    | Q(
                        status="archived",
                        completed_at__isnull=False,
                        archived_at__isnull=False,
                    )
                ),
                name="valid_item_status_timestamps",
            ),
        ]
        indexes = [
            models.Index(
                fields=("list", "status"),
                name="item_list_state_idx",
            ),
        ]

    def __str__(self):
        return self.text

class List(models.Model):
    owner = models.ForeignKey(
        "accounts.User",
        related_name="lists",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=100, default="Untitled list")
    updated_at = models.DateTimeField(auto_now=True)

    def get_absolute_url(self):
        return reverse("view_list", args=[self.id])


class Tag(models.Model):
    owner = models.ForeignKey(
        "accounts.User",
        related_name="tags",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=40)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "name"),
                name="unique_owner_tag_name",
            ),
        ]

    def __str__(self):
        return self.name
