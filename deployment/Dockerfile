# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the API requirements file and install dependencies
COPY api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the API code
COPY api/ .

# Expose the port Flask is running on
EXPOSE 5000

# Run the application
CMD ["python", "main.py"]
