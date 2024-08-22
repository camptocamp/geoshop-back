from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.contrib.auth.models import Permission, User
from django.contrib import admin

from django.shortcuts import render

def UserView(request):
    return render(request, "oidc_user.html")

class PermissionBackend(OIDCAuthenticationBackend):

    def get_perm_claim(self):
        return f"urn:zitadel:iam:org:project:{self.get_settings('ZITADEL_PROJECT')}:roles"
 
    def get_username(self, claims):
        return claims.get("sub")
 
    def create_user(self, claims):
        print ("HERECLAIMS:", claims)
        print ("CREATE_USER:", self.get_username(claims), claims[self.get_perm_claim()])

    def update_user(self, user, claims):
        print("UPDATE_USER: ", user, claims)
        return user
