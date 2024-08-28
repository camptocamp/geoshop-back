from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.contrib.auth.models import Permission, User
from django.contrib import admin
from django.shortcuts import render

ADMIN_ROLE = "admin"
STAFF_ROLE = "admin"

def updateUser(user, claims, roles):
    user.email = claims.get("email")
    user.first_name = claims.get("given_name")
    user.last_name = claims.get("family_name")
    user.is_superuser = ADMIN_ROLE in roles
    user.is_staff = STAFF_ROLE in roles
    return user

class PermissionBackend(OIDCAuthenticationBackend):

    def get_roles(self, claims):
        claim = f"urn:zitadel:iam:org:project:{self.get_settings('ZITADEL_PROJECT')}:roles"
        return claims.get(claim, {})

    def create_user(self, claims):
        roles = self.get_roles(claims)
        user = self.UserModel.objects.create_user(username=claims.get("sub"))
        updateUser(user, claims, roles)
        user.save()
        return user

    def update_user(self, user, claims):
        roles = self.get_roles(claims)
        updateUser(user, claims, roles).save()
        return user
