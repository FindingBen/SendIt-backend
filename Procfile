web: gunicorn 'backend.wsgi'
web: python manage.py collectstatic --noinput && gunicorn backend.wsgi