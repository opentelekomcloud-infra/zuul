# Copyright (c) 2019 Red Hat, Inc.
# Copyright (c) 2024 Acme Gating, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Set this to "-debug" to build a debug image (includes gdb, debug
# symbols, and is quite a bit larger).
ARG IMAGE_FLAVOR=

# Base images, defined as separate stages to allow for mirror selection or
# downstream customization via named contexts when built with docker buildx.

FROM artifactory.devops.telekom.de/dhi.io/python:3.11-debian12-dev${IMAGE_FLAVOR} AS zuul-base

# This is a mirror of:
# FROM docker.io/library/node:22-bookworm AS node-base
FROM artifactory.devops.telekom.de/dhi.io/node:22-debian13-dev AS node-base

# This is a mirror of:
# FROM golang:1.22-bookworm AS go-base
FROM artifactory.devops.telekom.de/dhi.io/golang:1.26-debian13-dev AS go-base

# Helper stage: extract build scripts from python-builder (public quay image)
FROM quay.io/opendevorg/python-builder:3.11-bookworm AS python-builder-tools

FROM artifactory.devops.telekom.de/dhi.io/python:3.11-debian12-dev AS builder-base
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies for the assemble script
# which is needed by _setup_hook.py (subprocess.call(['which', 'yarn']))
# gzip is needed by tar xvfz to extract the openshift client
RUN pip install --no-cache-dir bindep build wheel && \
    apt-get update && \
    apt-get install -y git which gzip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy build scripts from python-builder image
COPY --from=python-builder-tools /usr/local/bin/assemble /usr/local/bin/assemble
COPY --from=python-builder-tools /usr/local/bin/get-extras-packages /usr/local/bin/get-extras-packages
COPY --from=python-builder-tools /output/install-from-bindep /output/install-from-bindep

FROM node-base AS js-builder

COPY web /tmp/src
# Explicitly run the Javascript build
RUN cd /tmp/src && yarn install --frozen-lockfile && yarn list && yarn build

# We need skopeo >=v1.14.0 to negotioate with newer docker; once this
# is available in debian we can drop the custom build.
FROM go-base AS go-builder

# Keep this in sync with zuul-jobs ensure-skopeo
ARG SKOPEO_VERSION=v1.14.2
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get -y install libgpgme-dev libassuan-dev \
                       libbtrfs-dev libdevmapper-dev pkg-config && \
    git clone https://github.com/containers/skopeo /go/src/github.com/containers/skopeo &&\
    cd /go/src/github.com/containers/skopeo && \
    git checkout $SKOPEO_VERSION && \
    make bin/skopeo

FROM builder-base AS builder
ENV DEBIAN_FRONTEND=noninteractive

# Optional location of Zuul API endpoint.
ARG REACT_APP_ZUUL_API
# Optional flag to enable React Service Worker. (set to true to enable)
ARG REACT_APP_ENABLE_SERVICE_WORKER
# Kubectl/Openshift version/sha
ARG OPENSHIFT_URL=https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/4.11.20/openshift-client-linux-4.11.20.tar.gz
ARG OPENSHIFT_SHA=74f252c812932425ca19636b2be168df8fe57b114af6b114283975e67d987d11
ARG PBR_VERSION=

COPY . /tmp/src
COPY --from=js-builder /tmp/src/dist /tmp/src/zuul/web/static
RUN assemble

# The wheel install method doesn't run the setup hooks as the source based
# installations do so we have to call zuul-manage-ansible here. Remove
# /root/.local/share/virtualenv after because it adds wheels into /root
# that we don't need after the install step so are a waste of space.
RUN /output/install-from-bindep \
  && zuul-manage-ansible \
  && rm -rf /root/.local/share/virtualenv \
# Install openshift
  && mkdir /tmp/openshift-install \
  && curl -L $OPENSHIFT_URL -o /tmp/openshift-install/openshift-client.tgz \
  && cd /tmp/openshift-install/ \
  && echo $OPENSHIFT_SHA /tmp/openshift-install/openshift-client.tgz | sha256sum --check \
  && tar xvfz openshift-client.tgz -C /tmp/openshift-install

FROM zuul-base AS zuul
ENV DEBIAN_FRONTEND=noninteractive
ARG IMAGE_FLAVOR=

RUN --mount=from=builder,source=/output,target=/output \
  /output/install-from-bindep zuul_base

RUN useradd -u 10001 -m -d /var/lib/zuul -c "Zuul Daemon" zuul \
# This enables git protocol v2 which is more efficient at negotiating
# refs.  This can be removed after the images are built with git 2.26
# where it becomes the default.
  && git config --system protocol.version 2 \
# If we are building a debug image, add gdb
  && if [ "x$IMAGE_FLAVOR" = "x-debug" ]; then \
        apt-get update \
     && apt-get install -y gdb \
     && apt-get clean \
     && rm -rf /var/lib/apt/lists/*; \
     fi

VOLUME /var/lib/zuul
CMD ["/usr/local/bin/zuul"]

FROM zuul AS zuul-executor
ENV DEBIAN_FRONTEND=noninteractive
# In the hardened python image, python is installed in /opt/python (a
# symlink to /opt/python-3.11.16) and zuul-manage-ansible creates its
# ansible venvs at $sys.exec_prefix/lib/zuul — copy them to the matching
# runtime location.
COPY --from=builder /opt/python/lib/zuul/ /opt/python/lib/zuul
COPY --from=builder /tmp/openshift-install/oc /usr/local/bin/oc
COPY --from=go-builder /go/src/github.com/containers/skopeo/bin/skopeo /usr/local/bin/skopeo
COPY --from=go-builder /go/src/github.com/containers/skopeo/default-policy.json /etc/containers/policy.json
# The oc and kubectl binaries are large and have the same hash.
# Copy them only once and use a symlink to save space.
RUN ln -s /usr/local/bin/oc /usr/local/bin/kubectl

# Once we can use skopeo from Debian again, just change this to
# install skopeo; in the interim, this installes the runtime
# dependencies.
RUN apt-get update \
  && apt-get install -y libgpgme11 libdevmapper1.02.1 \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* \
  # bwrap unconditionally binds /etc/localtime and /etc/ld.so.cache —
  # create/regenerate them so the hardened image works with bubblewrap.
  && ln -sf /usr/share/zoneinfo/Etc/UTC /etc/localtime \
  && ldconfig

CMD ["/usr/local/bin/zuul-executor", "-f"]

FROM zuul AS zuul-fingergw
CMD ["/usr/local/bin/zuul-fingergw", "-f"]

FROM zuul AS zuul-launcher
CMD ["/usr/local/bin/zuul-launcher", "-f"]

FROM zuul AS zuul-merger
CMD ["/usr/local/bin/zuul-merger", "-f"]

FROM zuul AS zuul-scheduler
CMD ["/usr/local/bin/zuul-scheduler", "-f"]

FROM zuul AS zuul-web
CMD ["/usr/local/bin/zuul-web", "-f"]
