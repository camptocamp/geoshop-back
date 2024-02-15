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

### Run dev server without docker on a Linux based machine

- Create a virtual python environment and install the requirements.txt

- run the migrations on the DB and collectstatic:

    ```
    python manage.py migrate
    python manage.py collectstatic
    ```

- Create admin account and Extract group with permissions
    ```
    python manage.py fixturize
    ```

- Create a super user:
    ```
    python manage.py createsuperuser
    ```

- Run the application:
    ```
    python3 manage.py runserver
    ```

Access the application under the indicated address

### Run dev server without docker on Windows

You'll need to configure 3 paths to your GDAL installation according to `.env.sample`.

Then, we're going to:

 * Run migrations
 * Collect static files for the admin interface
 * Generate translations for your language
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
