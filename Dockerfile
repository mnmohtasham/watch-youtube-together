# Dockerfile
FROM python:3.9-slim-buster

#Set the working directory inside the container
WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Stage 5: Expose the port the app runs on
EXPOSE 5000

# Stage 6: Define the command to run your app
# We use gunicorn as a more robust production server than Flask's built-in one.
# It's better at handling multiple connections. We need to add it to requirements.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--worker-class", "eventlet", "-w", "1", "app:app"]