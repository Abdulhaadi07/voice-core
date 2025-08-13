# Voice Core

Voice Core

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## Settings

Moved to [settings](https://cookiecutter-django.readthedocs.io/en/latest/1-getting-started/settings.html).

## Environment / Configuration (`envs/.local/.django`)

Before running the project, configure the following environment variables:

### Database
```env
DATABASE_URL=<your_database_url>
```

### AWS credentials
```env
AWS_PROFILE=<your_aws_profile>
AWS_DEFAULT_REGION=<your_aws_region>
AWS_SHARED_CREDENTIALS_FILE=<path_to_credentials_file>
```

### Cognito credentials
```env
COGNITO_USER_POOL_ID=<your_user_pool_id>
COGNITO_APP_CLIENT_ID=<your_app_client_id>
COGNITO_APP_CLIENT_SECRET=<your_app_client_secret>
```

### Wazo Credentials
These are needed for user provisioning in Wazo:
```env
WAZO_ADMIN_USER=<admin_username>
WAZO_ADMIN_PASSWORD=<admin_password>
WAZO_API_URL=https://<wazo-server-url>
```

### Email credentials

```env
EMAIL_HOST=<smtp_host>
EMAIL_PORT=<smtp_port>
EMAIL_USE_TLS=<True_or_False>
EMAIL_USE_SSL=<True_or_False>
EMAIL_HOST_USER=<your_email>
EMAIL_HOST_PASSWORD=<your_email_password>
DEFAULT_FROM_EMAIL=<default_from_email>
EMAIL_TIMEOUT=<timeout_in_seconds>
DJANGO_EMAIL_BACKEND=<django_email_backend>
EMAIL_REPLY_TO=<reply_to_email>
```

## Basic Commands

### Setting Up Your Users

- To create a **normal user account**, just go to Sign Up and fill out the form. Once you submit it, you'll see a "Verify Your E-mail Address" page. Go to your console to see a simulated email verification message. Copy the link into your browser. Now the user's email should be verified and ready to go.

- To create a **superuser account**, use this command:

      $ python manage.py createsuperuser

For convenience, you can keep your normal user logged in on Chrome and your superuser logged in on Firefox (or similar), so that you can see how the site behaves for both kinds of users.

### Type checks

Running type checks with mypy:

    $ mypy voice_core

### Test coverage

To run the tests, check your test coverage, and generate an HTML coverage report:

    $ coverage run -m pytest
    $ coverage html
    $ open htmlcov/index.html

#### Running tests with pytest

    $ pytest

### Live reloading and Sass CSS compilation

Moved to [Live reloading and SASS compilation](https://cookiecutter-django.readthedocs.io/en/latest/2-local-development/developing-locally.html#using-webpack-or-gulp).

### Celery

This app comes with Celery.

To run a celery worker:

```bash
cd voice_core
celery -A config.celery_app worker -l info
```

Please note: For Celery's import magic to work, it is important _where_ the celery commands are run. If you are in the same folder with _manage.py_, you should be right.

To run [periodic tasks](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html), you'll need to start the celery beat scheduler service. You can start it as a standalone process:

```bash
cd voice_core
celery -A config.celery_app beat
```

or you can embed the beat service inside a worker with the `-B` option (not recommended for production use):

```bash
cd voice_core
celery -A config.celery_app worker -B -l info
```

## Deployment

The following details how to deploy this application.

### Docker

See detailed [cookiecutter-django Docker documentation](https://cookiecutter-django.readthedocs.io/en/latest/3-deployment/deployment-with-docker.html).


