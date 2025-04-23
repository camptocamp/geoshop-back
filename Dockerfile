FROM python:3.12.5-slim-bookworm
LABEL Maintainer="andrey.rusakov@camptocamp.com" Vendor="Camptocamp"

ENV  POETRY_NO_INTERACTION=1 \
     POETRY_VIRTUALENVS_CREATE=false \
     POETRY_CACHE_DIR='/var/cache/pypoetry' \
     POETRY_HOME='/usr/local'

WORKDIR /app/geoshop_back/
COPY poetry.lock pyproject.toml /app/geoshop_back/

RUN apt update && apt install -y libgdal-dev libffi-dev gettext && \
    pip install poetry && \
    poetry install --only=main --no-root

COPY . /app/geoshop_back/

# Copy default settings to settings only if there is no such file
RUN mv -vn /app/geoshop_back/default_settings.py /app/geoshop_back/settings.py

# Compile locales
RUN mv .env.sample .env
RUN OIDC_ENABLED=False python3 manage.py compilemessages --locale=fr
RUN rm -f .env

