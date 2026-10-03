"""
Payment Provider Interface and Dataclasses.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Dict, Any


@dataclass
class PaymentRequest:
    student: Any
    amount: Decimal
    currency: str = 'MMK'
    payment_type: str = 'course_purchase'
    course: Optional[Any] = None
    plan: Optional[Any] = None
    billing_period: str = 'one_time'
    method: str = 'other'
    reference: str = ''
    receipt: Optional[Any] = None
    note: str = ''
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PaymentResponse:
    success: bool
    status: str  # 'pending', 'processing', 'success', 'failed', 'cancelled'
    transaction_id: str
    amount: Decimal
    currency: str = 'MMK'
    message: str = ''
    redirect_url: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RefundResponse:
    success: bool
    refunded_amount: Decimal
    message: str = ''
    raw_data: Dict[str, Any] = field(default_factory=dict)


class BasePaymentProvider(ABC):
    """
    Abstract Payment Provider contract.
    Ensures that Myanmar E-Learning does not tightly couple business logic to a single provider.
    Supports manual slip review, mock sandbox testing, and future API gateways (KBZPay, WaveMoney, 2C2P, Stripe).
    """
    provider_code: str = 'base'
    display_name: str = 'Base Provider'

    @abstractmethod
    def process_payment(self, request: PaymentRequest) -> PaymentResponse:
        """Initiate or process a payment transaction."""
        pass

    @abstractmethod
    def process_refund(self, payment: Any, amount: Optional[Decimal] = None, reason: str = '') -> RefundResponse:
        """Process a full or partial refund."""
        pass

    def verify_webhook(self, payload: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
        """Verify authenticity of provider callback webhooks."""
        return {'verified': True, 'payload': payload}

    def query_status(self, reference: str) -> Optional[str]:
        """Query provider API for external status of a transaction."""
        return None
