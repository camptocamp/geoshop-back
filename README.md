# Geoshop Backend

## Requirements

* PostgreSQL >= 11 + PostGIS
* Python >= 3.9
* GDAL

## Getting started

Fork and clone this repository. Make a copy of `default_settings.py` and `.env.sample` file and adapt it to your environment settings:

```powershell
cp default_settings.py settings.py
cp .env.sample .env
```

`.env` will vary depending on the environements you're targetting.
`settings.py` will get the specific config of your project.

### Database

Create a `geoshop` user if not existing yet, set your password according to your `env.local`:

```sql
CREATE ROLE geoshop WITH LOGIN PASSWORD <password>;
```

Then, set up a database:

```sql
CREATE DATABASE geoshop OWNER geoshop;
REVOKE ALL ON DATABASE geoshop FROM PUBLIC;
```

Then connect to the geoshop database and create extensions:

```sql
CREATE EXTENSION postgis;
CREATE EXTENSION unaccent;
CREATE EXTENSION "uuid-ossp";
CREATE SCHEMA geoshop AUTHORIZATION geoshop;

-- TODO: Only if french is needed
CREATE TEXT SEARCH CONFIGURATION fr (COPY = simple);
ALTER TEXT SEARCH CONFIGURATION fr ALTER MAPPING FOR hword, hword_part, word
WITH unaccent, simple;
```

Now that the database is ready, you can start backend either with Docker or not.

### Run dev server without docker on Windows

You'll need to configure 3 paths to your GDAL installation according to `.env.sample`.

Then, we're going to:

 * Run migrations
 * Collect static files for the admin interface
 * Generate translations for your langage
 * Add minimal users to database

```shell
python manage.py migrate
python manage.py collectstatic
python manage.py compilemessages --locale=fr
python manage.py fixturize
```

Finally, you can run the server:

```shell
python manage.py runserver
```

## Run tests

```shell
python manage.py test
```

## Customize

custom.js in `api/templates/gis/admin`

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
OIDC_OP_BASE_URL = "..." # Your Zitadel instance url (something like https://geoshop-demo-abcdef.zitadel.cloud)
OIDC_REDIRECT_BASE_URL = "http://localhost:8000" # Where the service lives, different for local server or docker container
ZITADEL_PROJECT = "..."
OIDC_RP_CLIENT_ID = "..." # Zitadel Client ID
OIDC_RP_CLIENT_SECRET = "..." # Not needed in PKCE mode
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

| Zitadel role      | Geoshop       |
| ----------------- | ------------- |
| admin             | superuser     |
| staff             | staff         |
