import secrets
from decimal import Decimal
from typing import Optional, Any
from .base import BasePaymentProvider, PaymentRequest, PaymentResponse, RefundResponse


class SandboxGatewayProvider(BasePaymentProvider):
    """
    Automated sandbox test provider for testing, mock integrations, and instant fulfillment.
    Can be instructed via reference prefix:
    - 'FAIL-...' -> returns failed status
    - 'PROC-...' -> returns processing status
    - default -> returns instant success
    """
    provider_code = 'sandbox_gateway'
    display_name = 'Sandbox Test Gateway'

    def process_payment(self, request: PaymentRequest) -> PaymentResponse:
        ref = request.reference or f"SBX-{secrets.token_hex(4).upper()}"
        if ref.startswith('FAIL-'):
            return PaymentResponse(
                success=False,
                status='failed',
                transaction_id=ref,
                amount=request.amount,
                currency=request.currency,
                message='Sandbox payment failed as requested by test reference.',
            )
        elif ref.startswith('PROC-'):
            return PaymentResponse(
                success=True,
                status='processing',
                transaction_id=ref,
                amount=request.amount,
                currency=request.currency,
                message='Sandbox payment queued for asynchronous processing.',
            )
        return PaymentResponse(
            success=True,
            status='success',
            transaction_id=ref,
            amount=request.amount,
            currency=request.currency,
            message='Sandbox payment completed successfully.',
        )

    def process_refund(self, payment: Any, amount: Optional[Decimal] = None, reason: str = '') -> RefundResponse:
        refund_amount = amount or payment.amount
        return RefundResponse(
            success=True,
            refunded_amount=refund_amount,
            message="Sandbox payment refunded instantly.",
        )
