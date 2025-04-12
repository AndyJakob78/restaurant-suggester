# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Install system dependencies if needed (uncomment if any pip packages require them)
# RUN apt-get update && apt-get install -y build-essential libglib2.0-0 libsm6 libxext6 libxrender-dev

# Copy the API requirements file and install dependencies
COPY api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the API code
COPY api/ .

# Copy the ML module (as a package folder)
COPY ml/ ml/

# Copy the trained model file
COPY deployment/suggestion_model.pkl .

# Copy the email template folder
COPY email_service/ email_service/

# Ensure the ML module is recognized as a package
RUN touch ml/__init__.py

# Set the PORT environment variable to 8080 (used by Cloud Run)
ENV PORT 8080

# Expose port 8080
EXPOSE 8080

# Run the Flask app using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
