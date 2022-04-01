FROM registry.ci.openshift.org/ocp/builder:rhel-8-base-openshift-4.11

ENV container=oci

# FIXME(dulek): For some reason the local repo in OKD builds is disabled,
#               using sed to enable it. Ignoring fail as it won't work (nor
#               it's necessary) in OCP builds.
RUN (sed -i -e 's/enabled \?= \?0/enabled = 1/' /etc/yum.repos.d/built.repo || true) \
 && dnf install -y openshift-kuryr-controller \
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
        version="4.6.0" \
        com.redhat.component="kuryr-controller-container"
