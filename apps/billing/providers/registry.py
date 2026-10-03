from typing import Dict, Any, Type
from .base import BasePaymentProvider
from .manual import ManualTransferProvider
from .sandbox import SandboxGatewayProvider

_PROVIDERS: Dict[str, Any] = {
    'manual_transfer': ManualTransferProvider,
    'sandbox_gateway': SandboxGatewayProvider,
    'sandbox': SandboxGatewayProvider,
}

def register_payment_provider(code: str, provider: Any):
    _PROVIDERS[code] = provider

def get_payment_provider(code: str = 'manual_transfer') -> BasePaymentProvider:
    provider = _PROVIDERS.get(code, ManualTransferProvider)
    if isinstance(provider, type):
        return provider()
    return provider

def list_available_providers() -> list:
    seen = set()
    result = []
    for code, cls_or_inst in _PROVIDERS.items():
        if code in seen:
            continue
        seen.add(code)
        name = getattr(cls_or_inst, 'display_name', code)
        result.append({'code': code, 'name': name})
    return result
