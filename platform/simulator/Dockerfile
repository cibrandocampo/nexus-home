# Garage board simulator (development and tests only). Speaks the garage's /api/v1 on port 80, as a
# real board does. The code is copied in (rebuild after changing it); `make test-simulator` mounts
# the working copy.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    HOME=/tmp

WORKDIR /sim
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt
COPY pyproject.toml ./
COPY sim ./sim
COPY tests ./tests

USER 10001
EXPOSE 80
# Port 80, as a real board (the platform probes http://<ip>/api/v1). Docker lets unprivileged users
# bind low ports inside a container (net.ipv4.ip_unprivileged_port_start=0).
CMD ["uvicorn", "--factory", "sim.app:create_app", "--host", "0.0.0.0", "--port", "80", "--no-server-header"]
