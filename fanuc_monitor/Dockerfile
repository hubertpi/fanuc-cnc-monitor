FROM mcr.microsoft.com/dotnet/sdk@sha256:0eeb52c76e35a5431ca707ad2bc75e38006a05393045d8532ae44c15d9474523 AS build
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
# Fixed Ubuntu snapshot, rather than today's mutable package repository.
RUN sed -i -E 's#https?://(archive|security)\.ubuntu\.com/ubuntu/?#https://snapshot.ubuntu.com/ubuntu/20261009T000000Z/#g' /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /source
COPY worker/ ./worker/
RUN --network=none python3 worker/prepare_binding.py \
    && dotnet publish worker/Monitor.Worker.csproj -c Release -o /published --self-contained false \
    && dotnet /published/Monitor.Worker.dll --self-test

FROM mcr.microsoft.com/dotnet/runtime@sha256:5b280fe869ce058778531aa13d9a3ddf1efa0e889524904753da6fc48aada91e
ARG BUILD_VERSION=0.2.0
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="app" io.hass.arch="amd64"
RUN sed -i -E 's#https?://(archive|security)\.ubuntu\.com/ubuntu/?#https://snapshot.ubuntu.com/ubuntu/20261009T000000Z/#g' /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get update && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/monitor
COPY requirements.lock ./requirements.lock
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.lock
COPY app/ ./app/
COPY web/ ./web/
COPY --from=build /published/ /opt/worker/
COPY native/ /opt/monitor/native/
RUN python3 -c "import hashlib,json,pathlib; p=pathlib.Path('/opt/monitor/native'); m=json.loads((p/'provenance.json').read_text()); assert hashlib.sha256((p/m['filename']).read_bytes()).hexdigest()==m['sha256']" \
    && dotnet /opt/worker/Monitor.Worker.dll --native-self-test
ENV PYTHONUNBUFFERED=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
EXPOSE 8099
STOPSIGNAL SIGTERM
# Ingress only; there is deliberately no host port mapping in config.yaml.
CMD ["/opt/venv/bin/python", "-m", "app.main"]
