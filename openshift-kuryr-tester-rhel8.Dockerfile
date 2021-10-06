FROM ubi8

ENV container=oci

RUN yum install -y python3-devel python3-pbr python3-pip \
 && yum clean all \
 && rm -rf /var/cache/yum \
 && pip3 install tox

LABEL \
        io.k8s.description="This is a component of OpenShift Container Platform and provides a testing container for Kuryr service." \
        maintainer="Michal Dulko <mdulko@redhat.com>" \
        name="openshift/kuryr-tester" \
        io.k8s.display-name="kuryr-tester" \
        version="4.6.0" \
        com.redhat.component="kuryr-tester-container"
