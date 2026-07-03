#!/usr/bin/env bash
set -o errexit

# Retry migrations to tolerate short DB startup windows on platform boot.
max_attempts=10
attempt=1

until python libra/manage.py migrate; do
  if [ "$attempt" -ge "$max_attempts" ]; then
    echo "migrate failed after ${max_attempts} attempts"
    exit 1
  fi
  echo "migrate failed (attempt ${attempt}/${max_attempts}); retrying in 5s..."
  attempt=$((attempt + 1))
  sleep 5
done

python libra/manage.py load_initial_data
exec python -m gunicorn --bind 0.0.0.0:"$PORT" --chdir libra libra.wsgi:application
