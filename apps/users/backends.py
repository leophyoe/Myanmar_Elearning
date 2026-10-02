from typing import Optional
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from .services import authenticate_universal

User = get_user_model()


class UniversalAuthBackend(ModelBackend):
    """
    Universal Authentication Backend.
    Allows signing in with any of:
      1. Permanent Myanmar E-Learning Account ID (e.g. MEL-00012345)
      2. Verified Email address
      3. Username
    """

    def authenticate(
        self,
        request,
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs
    ):
        identifier = username or kwargs.get('identifier') or kwargs.get('email')
        if not identifier or not password:
            return None
        return authenticate_universal(identifier=identifier, password=password)

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
