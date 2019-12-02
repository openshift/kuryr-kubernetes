FROM openshift/origin-release:golang-1.11 AS builder

WORKDIR /go/src/github.com/openshift/kuryr-kubernetes
COPY . .
RUN go build -o /go/bin/kuryr-cni ./kuryr_cni

FROM ubi8

ENV container=oci
ARG OSLO_LOCK_PATH=/var/kuryr-lock

# FIXME(dulek): For some reason the local repos are disabled by default and
#               yum-config-manager is unable to enable them. Using sed for now.
RUN sed -i -e 's/enabled \?= \?0/enabled = 1/' /etc/yum.repos.d/*

COPY --from=builder /go/bin/kuryr-cni /kuryr-cni

RUN dnf install -y openshift-kuryr-cni iproute openvswitch \
 && dnf clean all \
 && rm -rf /var/cache/yum

ARG CNI_DAEMON=True
ENV CNI_DAEMON ${CNI_DAEMON}
ENV OSLO_LOCK_PATH ${OSLO_LOCK_PATH}

ENTRYPOINT /usr/libexec/kuryr/cni_ds_init

LABEL \
        io.k8s.description="This is a component of OpenShift Container Platform and provides a kuryr-cni service." \
        maintainer="Michal Dulko <mdulko@redhat.com>" \
        name="openshift/kuryr-cni" \
        io.k8s.display-name="kuryr-cni" \
        version="4.4.0" \
        com.redhat.component="kuryr-cni-container"
