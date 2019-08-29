FROM rhel7:latest

ENV container=oci

# FIXME(dulek): For some reason the local repos are disabled by default and
#               yum-config-manager is unable to enable them. Using sed for now.
RUN sed -i -e 's/enabled \?= \?0/enabled = 1/' /etc/yum.repos.d/built.repo

# FIXME(dulek): Until I'll figure out how to get OpenStack repos here, we need this hack.
RUN yum install --setopt=tsflags=nodocs -y \
    https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm \
    && printf '[openstack-stein]\n\
name=OpenStack Stein Repository\n\
baseurl=http://mirror.centos.org/centos/7/cloud/$basearch/openstack-stein/\n\
gpgcheck=0\n\
enabled=1\n' >> /etc/yum.repos.d/rdo-stein.repo

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
        version="3.11.0" \
        com.redhat.component="kuryr-controller-container"
