FROM quay.io/kuryr/golang:1.15 as builder

WORKDIR /go/src/opendev.com/kuryr-kubernetes
COPY . .
RUN go build -o /go/bin/kuryr-cni ./kuryr_cni

FROM registry.centos.org/centos:8
LABEL authors="Antoni Segura Puimedon<toni@kuryr.org>, Michał Dulko<mdulko@redhat.com>"

ARG UPPER_CONSTRAINTS_FILE="https://releases.openstack.org/constraints/upper/master"
ARG OSLO_LOCK_PATH=/var/kuryr-lock
ARG PKG_YUM_REPO=https://rdoproject.org/repos/openstack-victoria/rdo-release-victoria-2.el8.noarch.rpm

RUN yum upgrade -y \
    && yum install -y epel-release $PKG_YUM_REPO \
    && yum install -y --setopt=tsflags=nodocs python3-pip openvswitch sudo iproute libstdc++ pciutils kmod-libs \
    && yum install -y --setopt=tsflags=nodocs gcc gcc-c++ python3-devel git

COPY . /opt/kuryr-kubernetes

RUN pip3 --no-cache-dir install -U pip \
    && python3 -m pip --no-cache-dir install -c $UPPER_CONSTRAINTS_FILE /opt/kuryr-kubernetes \
    && cp /opt/kuryr-kubernetes/cni_ds_init /usr/bin/cni_ds_init \
    && mkdir -p /etc/kuryr-cni \
    && cp /opt/kuryr-kubernetes/etc/cni/net.d/* /etc/kuryr-cni \
    && yum -y history undo last \
    && yum clean all \
    && rm -rf /opt/kuryr-kubernetes \
    && mkdir ${OSLO_LOCK_PATH}

COPY --from=builder /go/bin/kuryr-cni /kuryr-cni

ARG CNI_DAEMON=True
ENV CNI_DAEMON ${CNI_DAEMON}
ENV OSLO_LOCK_PATH=${OSLO_LOCK_PATH}

ENTRYPOINT [ "cni_ds_init" ]
