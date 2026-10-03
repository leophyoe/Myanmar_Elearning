from rest_framework.authentication import TokenAuthentication
from rest_framework import exceptions


class BearerOrTokenAuthentication(TokenAuthentication):
    """
    Dual-header authentication supporting both 'Token <key>' and 'Bearer <key>'.
    Essential for mobile clients (iOS / Android) and standard API consumers.
    """
    keyword = 'Token'

    def authenticate(self, request):
        header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION', '')
        auth = header.split()

        if not auth or auth[0].lower() not in ('token', 'bearer'):
            return None

        if len(auth) == 1:
            raise exceptions.AuthenticationFailed('Invalid token header. No credentials provided.')
        elif len(auth) > 2:
            raise exceptions.AuthenticationFailed('Invalid token header. Token string should not contain spaces.')

        return self.authenticate_credentials(auth[1])
