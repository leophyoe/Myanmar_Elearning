import re
from django.core.exceptions import ValidationError


def validate_account_id(value: str) -> None:
    """
    Validates permanent Myanmar E-Learning Account ID format: MEL-XXXXXXXX (8 digits).
    Example: MEL-00012345
    """
    if not value:
        raise ValidationError("Account ID is required.")
    pattern = r'^MEL-\d{8}$'
    if not re.match(pattern, value):
        raise ValidationError("Invalid Account ID format. Must follow MEL-XXXXXXXX (e.g. MEL-00012345).")


def validate_strong_password(value: str) -> None:
    """
    Ensures passwords meet security requirements: minimum 8 characters.
    """
    if not value or len(value) < 8:
        raise ValidationError("Password must contain at least 8 characters.")
