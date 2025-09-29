import json
import requests
import time

from django.views.generic import View
from rest_framework_simplejwt.tokens import RefreshToken
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from authlib.jose import jwt
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from rest_framework.request import Request
from api.models import Identity

UserModel = get_user_model()

_defaultLanguage = 'de'
_supportedLanguages = ['de', 'fr', 'en']

def status(request):
    return {"OIDC_ENABLED": settings.FEATURE_FLAGS["oidc"]}


def _updateUser(user, claims):
    user.email = claims.get("email")
    user.first_name = claims.get("given_name")
    user.last_name = claims.get("family_name")
    identity, _ = Identity.objects.get_or_create(user=user)
    if not identity.email:
        identity.email = claims.get("email")
    identity.first_name = claims.get("given_name")
    identity.last_name = claims.get("family_name")

    userLanguage = (claims.get("locale") or _defaultLanguage).lower()
    if userLanguage not in _supportedLanguages:
        userLanguage = _defaultLanguage

    identity.language = userLanguage
    identity.save()
    user.save()


def _read_private_key(keyfile):
    with open(keyfile, "r") as f:
        data = json.load(f)
        return {
            "client_id": data["clientId"],
            "key_id": data["keyId"],
            "private_key": data["key"],
        }


class FrontendAuthentication(View):

    def __init__(self):
        super().__init__()
        self.private_key = _read_private_key(settings.OIDC_PRIVATE_KEYFILE)

    def _get_jwt_token(self):
        return jwt.encode(
            {"alg": "RS256", "kid": self.private_key["key_id"]},
            {
                "iss": self.private_key["client_id"],
                "sub": self.private_key["client_id"],
                "aud": settings.OIDC_OP_BASE_URL,
                "exp": int(time.time() + 3600),
                "iat": int(time.time()),
            },
            self.private_key["private_key"],
        )

    def _resolve_user_data(self, token: str):
        resp = requests.post(
            settings.OIDC_INTROSPECT_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": self._get_jwt_token(),
                "token": token,
            },
        )
        resp.raise_for_status()
        return json.loads(resp.content)

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        # Handle JSON error
        # TODO: Test missing id token
        # TODO: Localize error responser
        # TODO: Test same token multiple times
        # TODO: Test user does not exist
        # TODO: Test user exists, but unauthrized
        # TODO: Test user exists and authorized
        token_data = json.loads(request.body.decode("utf-8"))
        if "token" not in token_data:
            return JsonResponse({"error": "No token provided"}, status=400)

        user_data = self._resolve_user_data(token_data["token"])
        try:
            user = UserModel.objects.get(username=user_data["email"])
        except UserModel.DoesNotExist:
            user = UserModel.objects.create_user(username=user_data["email"])
        _updateUser(user, user_data)
        token = RefreshToken.for_user(user)
        return JsonResponse({"access": str(token.access_token), "refresh": str(token)})


class PermissionBackend(OIDCAuthenticationBackend):

    def authenticate_header(self, request: Request) -> str:
        return 'Bearer realm="api"'

    def create_user(self, claims):
        user = self.UserModel.objects.create_user(username=claims.get("email"))
        _updateUser(user, claims)
        return user

    def update_user(self, user, claims):
        _updateUser(user, claims)
        return user
