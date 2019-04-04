FROM rhel7:latest

ENV container=oci
ARG OSLO_LOCK_PATH=/var/kuryr-lock

COPY contrib/ci-repos.repo /etc/yum.repos.d/ci-repos.repo

RUN yum update -y \
 && yum install -y iproute bridge-utils openvswitch \
 && yum clean all \
 && rm -rf /var/cache/yum

# FIXME(dulek): For some reason the python-pbr is not in the repos in the CI,
#               let's just install it from binary now.
COPY * /kuryr-kubernetes-0.6.1/
RUN yum install -y /kuryr-kubernetes-0.6.1/python2-pbr-3.1.1-3.el7ar.noarch.rpm
RUN yum install -y python-devel rpm-build git

RUN bash /kuryr-kubernetes-0.6.1/tools/build-rpm.sh cni

ARG CNI_DAEMON=True
ENV CNI_DAEMON ${CNI_DAEMON}
ENV OSLO_LOCK_PATH ${OSLO_LOCK_PATH}

ENTRYPOINT /usr/libexec/kuryr/cni_ds_init

LABEL \
        io.k8s.description="This is a component of OpenShift Container Platform and provides a kuryr-cni service." \
        maintainer="Michal Dulko <mdulko@redhat.com>" \
        name="openshift/kuryr-cni" \
        io.k8s.display-name="kuryr-cni" \
        version="4.0.0" \
        com.redhat.component="kuryr-cni-container"
