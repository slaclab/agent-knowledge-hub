FROM python:3.12-slim

WORKDIR /app

COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes --only-binary :all: -r requirements.lock

COPY app/ ./app/

# Run as an unprivileged user (#033). The numeric USER lets Kubernetes verify runAsNonRoot.
# The root filesystem is read-only in the cluster, so Python writes no bytecode.
ENV PYTHONDONTWRITEBYTECODE=1
RUN groupadd --system --gid 1000 appuser \
    && useradd --system --uid 1000 --gid 1000 --no-create-home --shell /usr/sbin/nologin appuser
USER 1000:1000

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
