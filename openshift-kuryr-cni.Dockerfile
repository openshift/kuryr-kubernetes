FROM openshift/origin-release:golang-1.11 AS builder

WORKDIR /go/src/github.com/openshift/kuryr-kubernetes
COPY . .
RUN go build -o /go/bin/kuryr-cni ./kuryr_cni

FROM rhel7:latest

ENV container=oci
ARG OSLO_LOCK_PATH=/var/kuryr-lock

COPY --from=builder /go/bin/kuryr-cni /kuryr-cni

RUN yum update -y \
 && yum install -y openshift-kuryr-cni iproute bridge-utils openvswitch \
 && yum clean all \
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
        version="3.11.0" \
        com.redhat.component="kuryr-cni-container"
