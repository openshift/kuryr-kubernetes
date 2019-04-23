FROM rhel7:latest

ENV container=oci
ARG OSLO_LOCK_PATH=/var/kuryr-lock

# FIXME(dulek): Until I'll figure out how to get OpenStack repos here, we need this hack.
RUN yum install --setopt=tsflags=nodocs -y \
    https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm \
    https://www.rdoproject.org/repos/rdo-release.rpm

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
        version="4.0.0" \
        com.redhat.component="kuryr-cni-container"
