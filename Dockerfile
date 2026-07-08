FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy code vào container
COPY . .

# init database 
RUN python data/setup_db.py
EXPOSE 8000
CMD ["chainlit", "run", "demo.py", "--host", "0.0.0.0", "--port", "8000"]