# NetSpace IPAM backend image
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/app

# Copy the package before install so setuptools finds `app*`
COPY pyproject.toml README.md alembic.ini ./
COPY app ./app
COPY migrations ./migrations
RUN pip install .

# Dev convenience data dir (override NETSPACE_DATABASE_URL for real databases)
RUN mkdir -p /data
ENV NETSPACE_DATABASE_URL=sqlite:////data/netspace.db

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
