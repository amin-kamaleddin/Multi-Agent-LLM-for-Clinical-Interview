FROM python:3.11-slim

WORKDIR /app

# (Only keep packages you truly need)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your code (includes src/ and streamlit_app.py if it's at root)
COPY . .

# HF expects your app to listen on this port
ENV PORT=7860
EXPOSE 7860

# Streamlit's health endpoint
HEALTHCHECK CMD curl --fail http://localhost:${PORT}/_stcore/health || exit 1

# If your file is under src/, keep this; otherwise change to "streamlit_app.py"
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=${PORT}", "--server.address=0.0.0.0"]
