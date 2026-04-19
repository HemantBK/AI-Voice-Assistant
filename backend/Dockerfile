FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Dependency install — layer-cached.
# Copy only the metadata files + an empty package skeleton so pip can resolve
# `-e .[extras]` without requiring the full source tree. Dependencies change
# rarely; source changes often → this split keeps rebuilds fast.
# -----------------------------------------------------------------------------
COPY pyproject.toml requirements.txt ./
RUN mkdir -p app && touch app/__init__.py
RUN pip install --no-cache-dir -r requirements.txt

# Now overlay the real source. The editable install above points at ./app so
# code changes propagate without re-running pip.
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
