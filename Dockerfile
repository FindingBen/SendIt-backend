# Use an official Python runtime as a parent image
FROM python:3.x

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Define environment variables
ENV DJANGO_SETTINGS_MODULE=backend.settings
ENV CELERY_BROKER_URL=redis://default:0FxZAn6ojRjLzCYTpXlL@containers-us-west-43.railway.app:7431

# Run the Celery worker
CMD ["python", "-m", "celery", "-A", "backend", "worker", "--loglevel=info -P-solo"]
