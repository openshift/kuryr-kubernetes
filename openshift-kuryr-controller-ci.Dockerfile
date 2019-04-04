FROM centos:7

ENV container=oci

COPY contrib/ci-repos.repo /etc/yum.repos.d/ci-repos.repo

#RUN yum update -y \
# && yum clean all \
# && rm -rf /var/cache/yum

# FIXME(dulek): For some reason the python-pbr is not in the repos in the CI,
#               let's just install it from binary now.
COPY * /kuryr-kubernetes-0.6.1/
RUN yum install -y /kuryr-kubernetes-0.6.1/python2-pbr-3.1.1-3.el7ar.noarch.rpm
RUN yum install -y python-devel rpm-build git

RUN bash /kuryr-kubernetes-0.6.1/tools/build-rpm.sh controller

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
