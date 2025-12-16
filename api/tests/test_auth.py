import os
import json
import requests
import unittest
from django.conf import settings
from unittest import mock
from django.contrib.auth import get_user_model
from django.urls import reverse
from api.models import Identity
from rest_framework import status
from rest_framework.test import APITestCase

UserModel = get_user_model()
requestsPost = requests.post


def mockResponse(content):
    result = requests.Response()
    result.status_code = 200
    result._content = json.dumps(content)
    return result


class AuthViewsTests(APITestCase):
    """
    Test authentication
    """

    def setUp(self):
        self.username = "testuser"
        self.password = "testPa$$word"
        self.email = os.environ.get("EMAIL_TEST_TO", "test@example.com")

    def test_current_user(self):
        """
        Test current user view
        """
        data = {"username": self.username, "password": self.password}

        # URL using path name
        url = reverse("token_obtain_pair")

        user = UserModel.objects.create_user(
            username=self.username, email="test@example.com", password=self.password
        )
        self.assertEqual(user.is_active, 1, "Active User")

        # First post to get token
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        token = response.data["access"]

        # Next post/get's will require the token to connect
        self.client.credentials(HTTP_AUTHORIZATION="Bearer {0}".format(token))
        response = self.client.get(
            reverse("auth_current_user"), data={"format": "json"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.data["username"], self.username, "Gets his username")


@unittest.skipUnless(settings.FEATURE_FLAGS.get("oidc"), "OIDC tests disabled in settings")
class OidcAuthTests(APITestCase):

    def setUp(self):
        self.email = os.environ.get("EMAIL_TEST_TO", "test@example.com")
        self.fakeUser = {
            "email": self.email,
            "given_name": "GivenName",
            "family_name": "FamilyName",
        }


    @mock.patch("requests.post")
    def test_oidc_createuser(self, mock_post):
        mock_post.return_value = mockResponse(self.fakeUser)
        url = reverse("oidc_validate_token")

        # First post to get token
        response = self.client.post(url, data={"token": "fake_token"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        self.client.credentials(HTTP_AUTHORIZATION="Bearer {0}".format(response.json()["access"]))
        response = self.client.get(reverse("auth_current_user"), {"format": "json"})

        data = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(data, data | {"email": self.email, "username": self.email}, response.content)

        response = self.client.get(reverse("identity-detail", kwargs={"pk": data["identity_id"]}))
        identity = response.data
        self.assertEqual(identity, identity | {
                "email": self.email,
                "first_name": self.fakeUser["given_name"],
                "last_name": self.fakeUser["family_name"],
            },
            identity,
        )

    @mock.patch("requests.post")
    def test_oidc_updateuser(self, mock_post):
        existing_user = UserModel.objects.create_user(username=self.email, email=self.email)
        existing_user.save()
        identity, _ = Identity.objects.get_or_create(user=existing_user)
        identity.first_name = "Not our user first name"
        identity.last_name = "Not our user last name"
        identity.save()

        mock_post.return_value = mockResponse(self.fakeUser)
        url = reverse("oidc_validate_token")

        # First post to get token
        response = self.client.post(url, data={"token": "fake_token"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        self.client.credentials(HTTP_AUTHORIZATION="Bearer {0}".format(response.json()["access"]))
        response = self.client.get(reverse("auth_current_user"), {"format": "json"})

        data = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(data, data | {"email": self.email, "username": self.email}, response.content)

        response = self.client.get(reverse("identity-detail", kwargs={"pk": data["identity_id"]}))
        identity = response.data
        self.assertEqual(identity, identity | {
                "email": self.email,
                "first_name": self.fakeUser["given_name"],
                "last_name": self.fakeUser["family_name"],
            },
            identity,
        )

    # def test_noauth_401(self):
    #     url = reverse("validate-order")
    #     response = self.client.get(url, {"format": "json"})
    #     self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED, response.content)
