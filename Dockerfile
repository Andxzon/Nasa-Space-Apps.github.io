FROM python:3.13-slim-buster

WORKDIR /app

# Copy the .env file from the parent directory.
# Make sure the .env file is present in the website directory before building the image.
COPY .env .

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python3", "app.py"]