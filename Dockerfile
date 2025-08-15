FROM python:3.11-slim
WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your code (includes src/ and streamlit_app.py)
COPY . .

# Spaces expects your app to listen on this port
ENV PORT=7860
EXPOSE 7860

# Robust healthcheck (no curl needed)
HEALTHCHECK --interval=20s --timeout=5s --retries=5 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"7860\")}'); print('ok')" || exit 1

# Use *shell form* so $PORT is expanded
CMD streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true
