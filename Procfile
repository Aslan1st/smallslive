web: newrelic-admin run-program gunicorn --workers $WEB_CONCURRENCY --preload --max-requests 1000 --timeout 30 --pythonpath smallslive smallslive.wsgi
worker: celery -A smallslive worker -l info
