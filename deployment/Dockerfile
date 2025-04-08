# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the API requirements file and install dependencies
COPY api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the API code
COPY api/ .

# Copy the ML code (inference.py and train_model.py)
COPY ml/inference.py inference.py
COPY ml/train_model.py train_model.py
COPY deployment/suggestion_model.pkl .


# Copy the email_service directory
COPY email_service/ email_service/

# Set the PORT environment variable to 8080
ENV PORT 8080

# Expose port 8080
EXPOSE 8080

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
