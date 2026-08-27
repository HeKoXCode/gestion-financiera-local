#!/bin/sh
set -eu

python app/manage.py migrate --noinput
python app/manage.py collectstatic --noinput
exec "$@"
