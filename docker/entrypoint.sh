#!/bin/bash

# 1. Enable strict error handling (exit immediately on error)
set -e

# 2. Check whether database migration is enabled.
#    If enabled, run database migrations.
if [[ "${MIGRATION_ENABLED}" == "true" ]]; then
  echo "Running migrations"
  flask --app app.http.app db upgrade
fi

# 3. Check the runtime mode (api / celery) and execute different commands
if [[ "${MODE}" == "celery" ]]; then
  # 4. Start the Celery worker
  celery -A app.http.app.celery worker \
    -P ${CELERY_WORKER_CLASS:-prefork} \
    -c ${CELERY_WORKER_AMOUNT:-5} \
    --loglevel INFO
else
  # 5. Determine whether the API is running in development or production mode
  if [[ "${FLASK_ENV}" == "development" ]]; then
    # 6. Use Flask's built-in development server
    flask run \
      --host=${LLMOPS_BIND_ADDRESS:-0.0.0.0} \
      --port=${LLMOPS_PORT:-5001} \
      --debug
  else
    # 7. Use Gunicorn for production deployment,
    #    configuring workers, worker class, threads, timeout, and preload
    gunicorn \
      --bind "${LLMOPS_BIND_ADDRESS:-0.0.0.0}:${LLMOPS_PORT:-5001}" \
      --workers ${SERVER_WORKER_AMOUNT:-1} \
      --worker-class ${SERVER_WORKER_CLASS:-gthread} \
      --threads ${SERVER_THREAD_AMOUNT:-2} \
      --timeout ${GUNICORN_TIMEOUT:-600} \
      --preload \
      app.http.app:app
  fi
fi
