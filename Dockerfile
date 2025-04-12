# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the API requirements file and install dependencies
COPY api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy all code from `api/` into the container
COPY api/ .

# Copy the trained ML model
COPY deployment/suggestion_model.pkl .

# Set the PORT environment variable to 8080
ENV PORT 8080

# Expose port 8080
EXPOSE 8080

# Start the app with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
