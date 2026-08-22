"""Notifications composition root (+ event subscriber registration)."""

from __future__ import annotations

from django.conf import settings

from notifications.adapters.outbound.notifiers import ChannelNotifier
from notifications.adapters.outbound.persistence.repository import DjangoAlertRepository
from notifications.application.ports import AlertRepositoryPort, NotifierPort
from notifications.application.use_cases.evaluate_alerts import EvaluateAlerts
from notifications.application.use_cases.manage_alerts import ManageAlerts
from shared.composition import get_clock, get_event_bus

_subscribed = False


def build_alert_repository() -> AlertRepositoryPort:
    return DjangoAlertRepository()


def build_notifier() -> NotifierPort:
    return ChannelNotifier()


def build_manage_alerts() -> ManageAlerts:
    return ManageAlerts(repository=build_alert_repository())


def build_evaluate_alerts() -> EvaluateAlerts:
    return EvaluateAlerts(
        repository=build_alert_repository(),
        notifier=build_notifier(),
        clock=get_clock(),
        cooldown_seconds=getattr(settings, "ALERT_COOLDOWN_SECONDS", 21600),
    )


def register_subscribers() -> None:
    """Subscribe alert evaluation to the collection/price-change events (idempotent)."""
    global _subscribed
    if _subscribed:
        return
    from notifications.adapters.inbound.events import subscribers
    from shared.events import PriceChanged, ProductsCollected

    bus = get_event_bus()
    bus.subscribe(ProductsCollected, subscribers.on_products_collected)
    bus.subscribe(PriceChanged, subscribers.on_price_changed)
    _subscribed = True
