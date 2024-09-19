import os
import json
import requests
from requests.auth import HTTPBasicAuth
import secrets
import time

from django.core import serializers
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from authlib.jose import jwt
from django.http import HttpResponse
from django.conf import settings
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import get_user_model

UserModel = get_user_model()

KEY_FILE = "/home/arusakov/devel/c2c/extract/geoshop-back/user_key.json"
ZITADEL_OIDC_DOMAIN = "https://geoshop-demo-syazg0.zitadel.cloud"
ZITADEL_INTROSPECT_URL = f"{ZITADEL_OIDC_DOMAIN}/oauth/v2/introspect"

def status(request):
    return {
        "OIDC_ENABLED": settings.OIDC_ENABLED,
    }


def updateUser(user, claims):
    user.email = claims.get("email")
    user.first_name = claims.get("given_name")
    user.last_name = claims.get("family_name")
    return user

def private_key():
    with open(KEY_FILE, "r") as f:
        data = json.load(f)
        return {
            "client_id": data["clientId"],
            "key_id": data["keyId"],
            "private_key": data["key"],
        }

def get_jwt_token(oidc_domain: str):
    prk = private_key()
    payload = {
        "iss": prk["client_id"],
        "sub": prk["client_id"],
        "aud": oidc_domain,
        "exp": int(time.time() + 3600),
        "iat": int(time.time()),
    }
    return jwt.encode(
        {"alg": "RS256", "kid": prk["key_id"]}, payload, prk["private_key"]
    )

@csrf_exempt
def validate_token(request):
    # Handle JSON error
    # TODO: Test missing id token
    # TODO: Localize error response
    # TODO: Test same token multiple times
    data = json.loads(request.body.decode("utf-8"))
    if "token" not in data:
        return JsonResponse({"error": "No token provided"}, status=400)

    resp = requests.post(
        ZITADEL_INTROSPECT_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": get_jwt_token(ZITADEL_OIDC_DOMAIN),
            "token": data["token"],
        },
    )
    resp.raise_for_status()
    user_data = json.loads(resp.content)

    UserModel = get_user_model()
    user = UserModel.objects.get(username=user_data["email"])
    if not user:
        user = UserModel.objects.create_user(username=user_data["email"])
    updateUser(user, user_data)
    user.save()

    return JsonResponse({"user": {"id": user.id, "username": user.username}})


class PermissionBackend(OIDCAuthenticationBackend):

    def create_user(self, claims):
        user = self.UserModel.objects.create_user(username=claims.get("email"))
        updateUser(user, claims)
        user.save()
        return user

    def update_user(self, user, claims):
        updateUser(user, claims).save()
        return user
