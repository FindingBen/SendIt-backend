from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from asgiref.sync import sync_to_async

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


def get_token_from_scope(scope):
    query_string = scope.get("query_string", b"").decode()
    query_params = parse_qs(query_string)
    token_list = query_params.get("token")
    return token_list[0] if token_list else None


@sync_to_async
def get_user_from_token(token):
    # Lazy imports — CRITICAL
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import AnonymousUser

    User = get_user_model()
    jwt_auth = JWTAuthentication()

    try:
        validated_token = jwt_auth.get_validated_token(token)
        return jwt_auth.get_user(validated_token)
    except (InvalidToken, TokenError, User.DoesNotExist):
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        # Lazy import again
        from django.contrib.auth.models import AnonymousUser

        scope["user"] = AnonymousUser()

        token = get_token_from_scope(scope)
        if token:
            scope["user"] = await get_user_from_token(token)

        return await super().__call__(scope, receive, send)
