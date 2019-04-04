FROM rhel7:latest

ENV container=oci

RUN yum update -y \
 && yum install -y python-devel python-pbr python-pip \
 && yum clean all \
 && rm -rf /var/cache/yum \
 && pip install tox

LABEL \
        io.k8s.description="This is a component of OpenShift Container Platform and provides a testing container for Kuryr service." \
        maintainer="Michal Dulko <mdulko@redhat.com>" \
        name="openshift/kuryr-tester" \
        io.k8s.display-name="kuryr-tester" \
        version="4.0.0" \
        com.redhat.component="kuryr-tester-container"
