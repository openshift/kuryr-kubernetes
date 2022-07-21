FROM registry.ci.openshift.org/ocp/builder:rhel-8-base-openshift-4.12

RUN dnf install -y --setopt=tsflags=nodocs python3-pip \
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
 && rm -rf /opt/kuryr-kubernetes \
 && rm -rf $REMOTE_SOURCES_DIR

CMD [ "--config-dir", "/etc/kuryr" ]
ENTRYPOINT [ "kuryr-k8s-controller" ]

LABEL \
        io.k8s.description="This is a component of OpenShift Container Platform and provides a kuryr-controller service." \
        maintainer="Michal Dulko <mdulko@redhat.com>" \
        name="openshift/kuryr-controller" \
        io.k8s.display-name="kuryr-controller" \
        version="4.6.0" \
        com.redhat.component="kuryr-controller-container"
