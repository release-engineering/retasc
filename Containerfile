FROM quay.io/fedora/python-312:20240904@sha256:82cee3f53ef440f9d0e0f7a98ea7ce9328a698a7f16595af699fb8a9e97ba034 AS builder

# builder should use root to install/create all files
USER root

# hadolint ignore=DL3033,DL4006,SC2039,SC3040
RUN set -exo pipefail \
    && mkdir -p /mnt/rootfs \
    # install runtime dependencies
    && yum install -y \
        --installroot=/mnt/rootfs \
        --releasever=/ \
        --setopt install_weak_deps=false \
        --nodocs \
        --disablerepo=* \
        --enablerepo=fedora,updates \
        python3 \
    && yum --installroot=/mnt/rootfs clean all \
    && rm -rf /mnt/rootfs/var/cache/* /mnt/rootfs/var/log/dnf* /mnt/rootfs/var/log/yum.* \
    # https://python-poetry.org/docs/master/#installing-with-the-official-installer
    && curl -sSL --proto "=https" https://install.python-poetry.org | python3 - \
    && python3 -m venv /venv

ENV \
    PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Copy only specific files to avoid accidentally including any generated files
# or secrets.
COPY src ./src
COPY container ./container
COPY \
    pyproject.toml \
    poetry.lock \
    README.md \
    ./

# hadolint ignore=SC1091
RUN set -ex \
    && export PATH=/root/.local/bin:$PATH \
    && . /venv/bin/activate \
    && poetry build --format=wheel \
    && version=$(poetry version --short) \
    && pip install --no-cache-dir dist/retasc-"$version"-py3*.whl \
    && deactivate \
    && mv /venv /mnt/rootfs \
    && mkdir -p /mnt/rootfs/src/container \
    && cp -v container/entrypoint.sh /mnt/rootfs/src/container

# This is just to satisfy linters
USER 1001

# --- Final image
FROM scratch
ARG GITHUB_SHA
ARG EXPIRES_AFTER
LABEL \
    name="retasc" \
    vendor="ReTaSC developers" \
    summary="Release Task Schedule Curator (ReTaSC)" \
    description="App for planning product release work in Jira based on schedules in Product Pages" \
    maintainer="Red Hat, Inc." \
    license="GPLv3+" \
    url="https://github.com/release-engineering/retasc" \
    vcs-type="git" \
    vcs-ref=$GITHUB_SHA \
    io.k8s.display-name="ReTaSC" \
    quay.expires-after=$EXPIRES_AFTER

ENV \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1 \
    WEB_CONCURRENCY=8

COPY --from=builder /mnt/rootfs/ /
COPY --from=builder \
    /etc/yum.repos.d/fedora.repo \
    /etc/yum.repos.d/fedora-updates.repo \
    /etc/yum.repos.d/
WORKDIR /src

USER 1001
EXPOSE 8080

# Validate virtual environment
RUN /src/container/entrypoint.sh python -c \
      'from retasc import __version__; print(__version__)' \
    && /src/container/entrypoint.sh retasc --version \
    && /src/container/entrypoint.sh retasc --help

ENTRYPOINT ["/src/container/entrypoint.sh"]
CMD ["retasc", "--help"]
