-- CREATE ROLE geoshop WITH LOGIN PASSWORD geoshop;
--
-- CREATE DATABASE geoshop OWNER geoshop;
-- REVOKE ALL ON DATABASE geoshop FROM PUBLIC;

CREATE EXTENSION postgis;
CREATE EXTENSION unaccent;
CREATE EXTENSION "uuid-ossp";

CREATE SCHEMA geoshop AUTHORIZATION geoshop;

CREATE TEXT SEARCH CONFIGURATION fr (COPY = simple);

ALTER TEXT SEARCH CONFIGURATION fr ALTER MAPPING FOR hword, hword_part, word
WITH unaccent, simple;