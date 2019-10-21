FROM ubi8

ENV container=oci

# FIXME(dulek): For some reason the local repos are disabled by default and
#               yum-config-manager is unable to enable them. Using sed for now.
RUN sed -i -e 's/enabled \?= \?0/enabled = 1/' /etc/yum.repos.d/*

RUN dnf install -y openshift-kuryr-controller \
 && dnf clean all \
 && rm -rf /var/cache/yum

USER kuryr
CMD ["--config-dir", "/etc/kuryr"]
ENTRYPOINT [ "/usr/bin/kuryr-k8s-controller" ]

LABEL \
        io.k8s.description="This is a component of OpenShift Container Platform and provides a kuryr-controller service." \
        maintainer="Michal Dulko <mdulko@redhat.com>" \
        name="openshift/kuryr-controller" \
        io.k8s.display-name="kuryr-controller" \
        version="4.3.0" \
        com.redhat.component="kuryr-controller-container"
