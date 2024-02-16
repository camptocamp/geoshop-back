FROM ghcr.io/osgeo/gdal:ubuntu-small-3.5.2

RUN apt-get update --fix-missing && \
    apt-get install gettext python3-pip libcairo2-dev build-essential python3-dev \
    pipenv python3-setuptools python3-wheel python3-cffi libcairo2 libpango-1.0-0 \
    libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info libpq-dev -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /app/geoshop_back/requirements.txt
WORKDIR /app/geoshop_back/
RUN pip3 install -r requirements.txt

# Update C env vars so compiler can find gdal
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
ENV PYTHONUNBUFFERED 1

COPY . /app/geoshop_back/

# FIXME: why was this needed?
# RUN mkdir /mnt/geoshop_data
