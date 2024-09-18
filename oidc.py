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
from django.http import JsonResponse,HttpResponse
from django.contrib.auth import get_user_model

UserModel = get_user_model()

KEY_FILE="/home/arusakov/devel/c2c/extract/geoshop-back/user_key.json"

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
            "private_key": data["key"]
        }

@csrf_exempt
def validate_token(request):
    # Handle JSON error
    data = json.loads(request.body.decode("utf-8"))
    prk = private_key()
    # TODO: Test missing id token
    # TODO: Localize error response
    # TODO: Test same token multiple times
    if "token" not in data:
        return JsonResponse({"error": "No token provided"}, status=400)

    token_string = data["token"]
    url = "https://geoshop-demo-syazg0.zitadel.cloud/oauth/v2/introspect"
    payload = {
        "iss": prk["client_id"],
        "sub": prk["client_id"],
        "aud": "https://geoshop-demo-syazg0.zitadel.cloud",
        "exp": int(time.time() + 3600),
        "iat": int(time.time())
    }
    header = {"alg": "RS256", "kid": prk["key_id"]}
    jwt_token = jwt.encode(header, payload, prk["private_key"])
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    data = {
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": jwt_token,
        "token": token_string,
    }
    resp = requests.post(url, headers=headers, data=data)
    resp.raise_for_status()
    user_data = json.loads(resp.content)

    UserModel = get_user_model()

    user = UserModel.objects.get(username=user_data["email"])
    if not user:
        user = UserModel.objects.create_user(username=user_data["email"])
    updateUser(user, user_data)
    user.save()

    return JsonResponse({"user": serializers.serialize("json", [user])})


class PermissionBackend(OIDCAuthenticationBackend):

    def create_user(self, claims):
        user = self.UserModel.objects.create_user(username=claims.get("email"))
        updateUser(user, claims)
        user.save()
        return user

    def update_user(self, user, claims):
        updateUser(user, claims).save()
        return user
