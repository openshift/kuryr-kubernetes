FROM registry.ci.openshift.org/ocp/builder:rhel-8-golang-1.18-openshift-4.12 AS builder

WORKDIR /go/src/github.com/openshift/kuryr-kubernetes
COPY . .
WORKDIR /go/src/github.com/openshift/kuryr-kubernetes/kuryr_cni
RUN go build -o /go/bin/kuryr-cni ./pkg

FROM registry.ci.openshift.org/ocp/builder:rhel-8-base-openshift-4.12

ARG OSLO_LOCK_PATH=/var/kuryr-lock

COPY --from=builder /go/bin/kuryr-cni /kuryr-cni

COPY ./images/iptables-scripts/iptables /usr/sbin/
COPY ./images/iptables-scripts/ip6tables /usr/sbin/

RUN dnf install -y --setopt=tsflags=nodocs python3-pip iproute openvswitch \
 && dnf install -y --setopt=tsflags=nodocs python3-devel git gcc gcc-c++ libffi-devel

COPY . /opt/kuryr-kubernetes
# Cachito stuff
COPY $REMOTE_SOURCES $REMOTE_SOURCES_DIR

ARG VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
# This is enough to activate a venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN source $REMOTE_SOURCES_DIR/cachito-gomod-with-deps/cachito.env \
 # Needed to have rust wheel
 && pip3 --no-cache-dir install --upgrade setuptools pip \
 && pip3 --no-cache-dir install wheel \
 && pip3 --no-cache-dir install -r /opt/kuryr-kubernetes/kuryr-requirements.txt /opt/kuryr-kubernetes \
 && dnf -y history undo last \
 && dnf clean all \
 && cp /opt/kuryr-kubernetes/cni_ds_init /opt/cni_ds_init \
 && mkdir -p /etc/kuryr-cni \
 && cp /opt/kuryr-kubernetes/etc/cni/net.d/10-kuryr.conflist /etc/kuryr-cni/10-kuryr.conflist \
 && rm -rf /opt/kuryr-kubernetes \
 && rm -rf $REMOTE_SOURCES_DIR

ARG CNI_DAEMON=True
ENV CNI_DAEMON ${CNI_DAEMON}
ENV OSLO_LOCK_PATH ${OSLO_LOCK_PATH}

ENTRYPOINT /opt/cni_ds_init

LABEL \
        io.k8s.description="This is a component of OpenShift Container Platform and provides a kuryr-cni service." \
        maintainer="Michal Dulko <mdulko@redhat.com>" \
        name="openshift/kuryr-cni" \
        io.k8s.display-name="kuryr-cni" \
        version="4.6.0" \
        com.redhat.component="kuryr-cni-container"
