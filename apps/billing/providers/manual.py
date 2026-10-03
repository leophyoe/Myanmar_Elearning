from decimal import Decimal
from typing import Optional, Any
from .base import BasePaymentProvider, PaymentRequest, PaymentResponse, RefundResponse


class ManualTransferProvider(BasePaymentProvider):
    """
    Manual payment processing for Myanmar local channels:
    - KBZ Pay (KPay)
    - Wave Money (WavePay)
    - Bank Transfer (KBZ, CB, AYA)
    Payment is registered in PENDING status for administrative slip review.
    """
    provider_code = 'manual_transfer'
    display_name = 'Manual Bank / Wallet Transfer'

    def process_payment(self, request: PaymentRequest) -> PaymentResponse:
        ref = request.reference or f"MANUAL-{request.student.id.hex[:6].upper()}"
        return PaymentResponse(
            success=True,
            status='pending',
            transaction_id=ref,
            amount=request.amount,
            currency=request.currency,
            message='Payment slip registered. Awaiting administrator verification.',
        )

    def process_refund(self, payment: Any, amount: Optional[Decimal] = None, reason: str = '') -> RefundResponse:
        refund_amount = amount or payment.amount
        return RefundResponse(
            success=True,
            refunded_amount=refund_amount,
            message=f"Manual transfer refund authorized for {payment.student.username}.",
        )
