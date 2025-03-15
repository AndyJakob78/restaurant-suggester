# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the API requirements file and install dependencies
COPY api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the API code
COPY api/ .

# Copy the email_service directory into the container
COPY email_service/ email_service/

# Set the PORT environment variable to 8080
ENV PORT 8080

# Expose port 8080 (Cloud Run expects your app to listen on this port)
EXPOSE 8080

# Run the application
CMD ["python", "main.py"]
