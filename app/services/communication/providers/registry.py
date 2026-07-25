"""Pluggable communication provider registry."""

from __future__ import annotations

from app.services.communication.providers.base import CommunicationProvider

_PROVIDERS: dict[str, CommunicationProvider] = {}


def register_provider(provider: CommunicationProvider) -> None:
    _PROVIDERS[provider.channel] = provider


def get_provider(channel: str) -> CommunicationProvider | None:
    return _PROVIDERS.get(channel)


def list_providers() -> dict[str, CommunicationProvider]:
    return dict(_PROVIDERS)


def reset_providers() -> None:
    _PROVIDERS.clear()


def install_default_providers(*, bot=None) -> None:
    from app.services.communication.providers.email import EmailProvider
    from app.services.communication.providers.push import MobilePushProvider
    from app.services.communication.providers.sms import SmsProvider
    from app.services.communication.providers.telegram import TelegramProvider

    reset_providers()
    register_provider(TelegramProvider(bot=bot))
    register_provider(MobilePushProvider())
    register_provider(SmsProvider())
    register_provider(EmailProvider())
