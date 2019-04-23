FROM rhel7:latest

ENV container=oci

# FIXME(dulek): Until I'll figure out how to get OpenStack repos here, we need this hack.
RUN yum install --setopt=tsflags=nodocs -y \
    https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm \
    https://www.rdoproject.org/repos/rdo-release.rpm

RUN yum update -y \
 && yum install -y openshift-kuryr-controller \
 && yum clean all \
 && rm -rf /var/cache/yum

USER kuryr
CMD ["--config-dir", "/etc/kuryr"]
ENTRYPOINT [ "/usr/bin/kuryr-k8s-controller" ]

LABEL \
        io.k8s.description="This is a component of OpenShift Container Platform and provides a kuryr-controller service." \
        maintainer="Michal Dulko <mdulko@redhat.com>" \
        name="openshift/kuryr-controller" \
        io.k8s.display-name="kuryr-controller" \
        version="4.0.0" \
        com.redhat.component="kuryr-controller-container"
