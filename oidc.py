from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.contrib.auth.models import Permission, User
from django.contrib import admin
from django.shortcuts import render

def updateUser(user, claims):
    user.email = claims.get("email")
    user.first_name = claims.get("given_name")
    user.last_name = claims.get("family_name")
    return user

class PermissionBackend(OIDCAuthenticationBackend):

    def create_user(self, claims):
        user = self.UserModel.objects.create_user(username=claims.get("email"))
        updateUser(user, claims)
        user.save()
        return user

    def update_user(self, user, claims):
        updateUser(user, claims).save()
        return user
