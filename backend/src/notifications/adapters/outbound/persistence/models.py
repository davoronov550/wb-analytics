"""Notifications persistence models (Django ORM)."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class AlertRuleModel(models.Model):
    """A user's alert rule."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alert_rules"
    )
    kind = models.CharField(max_length=16)  # abs_below | pct_drop
    value = models.DecimalField(max_digits=10, decimal_places=2)
    channel = models.CharField(max_length=16)  # email | telegram
    target_wb_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    target_query = models.CharField(max_length=200, null=True, blank=True, db_index=True)
    active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications_alert_rule"

    def __str__(self) -> str:
        return f"Alert #{self.pk} {self.kind} {self.value}"


class AlertEventModel(models.Model):
    """A firing of a rule (for dedup/cooldown and history)."""

    rule = models.ForeignKey(AlertRuleModel, on_delete=models.CASCADE, related_name="events")
    wb_id = models.BigIntegerField()
    triggered_at = models.DateTimeField()
    delivered = models.BooleanField(default=True)

    class Meta:
        db_table = "notifications_alert_event"
        indexes = [models.Index(fields=["rule", "wb_id", "triggered_at"])]
