# Geoshop Backend

## Requirements

* PostgreSQL >= 17 + PostGIS
* Python >= 3.13
* GDAL
* gettext

## Quick start

In a container:
```bash
cp .env.sample .env
sed -i 's/PGHOST=localhost/PGHOST=db/g' .env

docker compose up -d
docker compose exec api bash -c "python manage.py seed"
```

Without a container:
```bash
cp .env.sample .env
sed -i 's/PGHOST=db/PGHOST=localhost/g' .env
cp -vn default_settings.py settings.py
docker compose up -d db

# Start a virtual environment
python -m venv .venv
source .venv/bin/activate
pip install poetry
poetry install --no-root

python manage.py migrate
python manage.py collectstatic
python manage.py compilemessages --locale=de
python manage.py fixturize
python manage.py seed

python manage.py runserver

```

Now, go to [http://localhost:8000](http://localhost:8000) and log in with ```admin```, ```Test1234```

To use it with frontend, see the [OIDC authentication](#oidc-authentication) part.

### Testing

```bash
python manage.py seed
python manage.py test
```

## Make translations strings

```shell
django-admin makemessages -a --no-location
```

# OIDC authentication

## Glossary

* [OpenID](https://openid.net/) is an open standard and decentralized authentication protocol.
* [OAuth](https://oauth.net/) or Open Authorization is an **authorization** standard and protocol.
* [OIDC]() or OpenID Connect is an **authentication** protocol based on OAuth2.0 standard, a third generation of an OpenID technology.
* [Zitadel](https://zitadel.ch) - authentication management service, a single point to configure permissions for our services.

For OpenID authentication, Geoshop uses [mozilla-django-oidc](https://github.com/mozilla/mozilla-django-oidc) library, published under [Mozilla Public License 2.0](https://github.com/mozilla/mozilla-django-oidc/blob/main/LICENSE).

## Django configuration

.env variables are usually enough:
```python
OIDC_ENABLED = True|False # Toggle Zitadel authentication globally.
OIDC_OP_BASE_URL = "..." # Your Zitadel instance url (something like https://geoshop-demo-abcdef.zitadel.cloud)
OIDC_REDIRECT_BASE_URL = "http://localhost:8000" # Where the service lives, different for local server or docker container
ZITADEL_PROJECT = "..."
OIDC_RP_CLIENT_ID = "..." # Zitadel Client ID
```

### Extended description
urls.py - special configuration required because Zitadel strips out trailing slashes in the redirect URLs, but Mozilla OIDC urls.py requires them.
```python
...
    path("oidc/callback", OIDCCallbackClass.as_view(), name="oidc_authentication_callback"),
    path("oidc/authenticate/",  OIDCAuthenticateClass.as_view(), name="oidc_authentication_init"),
    path("oidc/logout", OIDCLogoutView.as_view(), name="oidc_logout"),
...
```

settings.py - extra app, middleware and authentication backend
```python
INSTALLED_APPS=[
    ...
    'mozilla_django_oidc',
    ...
]

MIDDLEWARE=[
    ...
    'mozilla_django_oidc.middleware.SessionRefresh',
    ...
]

AUTHENTICATION_BACKENDS = (
    ...
    "oidc.PermissionBackend",
    ...
)
```

## Zitadel side

*[Zitadel Django Tutorial](https://zitadel.com/docs/sdk-examples/python-django)*

### An overview

1. level is "Organization" - that part is mostly about configuring your Zitadel users, permissions and billing.
1. level is "Instance" - place where you configure your services and your service users, permissions and other authorization parameters. There could be multiple (e.g. -dev, -prod)
1. level is "Project" - users and roles here. Each project is your service that can authenticate and authorize users defined on the "Instance" level
1. level is "Application" - authorization and authentication tokens and methods,


## Roles and permissions

Zitadel roles and their Geoshop equivalents:

| Zitadel role | Geoshop   |
| ------------ | --------- |
| admin        | superuser |
| staff        | staff     |
