# Use official lightweight Python image
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Copy all local project files to /app in the container
COPY . /app

# Install dependencies (if you have requirements.txt)
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8000 for Django development server
EXPOSE 8000

# Run the Django development server
CMD ["python3", "manage.py", "runserver", "0.0.0.0:8000"]
