from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.contrib.auth.models import Permission, User
from django.contrib import admin
from django.shortcuts import render

def UserView(request):
    return render(request, "oidc_user.html")

ADMIN_ROLE = "admin"
USER_ROLE = "user"

class PermissionBackend(OIDCAuthenticationBackend):

    def get_roles(self, claims):
        claim = f"urn:zitadel:iam:org:project:{self.get_settings('ZITADEL_PROJECT')}:roles"
        return claims.get(claim, {})
 
    def create_user(self, claims):
        roles = self.get_roles(claims)
        if not roles:
            return self.UserModel.objects.none()

        user = self.UserModel.objects.create_user(claims.get("sub"), claims.get("email"))
        user.first_name = claims.get("given_name")
        user.last_name = claims.get("family_name")
        user.is_superuser = ADMIN_ROLE in roles
        user.save()

        return user

    def update_user(self, user, claims):
        roles = self.get_roles(claims)
        user.first_name = claims.get("given_name")
        user.last_name = claims.get("family_name")
        user.is_superuser = ADMIN_ROLE in roles
        user.save()
       
        return user
