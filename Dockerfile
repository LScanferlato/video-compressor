FROM python:3.11-alpine

# Installa ffmpeg
RUN apk add --no-cache ffmpeg bash

# Lavora nella cartella /app
WORKDIR /app

# Crea ambiente virtuale per evitare "externally-managed-environment"
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Copia e installa dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia l'app
COPY . .

# Espone la porta
EXPOSE 5000

# Avvia l'app
CMD ["python", "app.py"]

