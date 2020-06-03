#!/bin/bash -x

version=4.6.1
source_path=_output/SOURCES

mkdir -p ${source_path}

# NOTE(dulek): rpmbuild requires that inside the tar there will be a
#              ${service}-${version} directory, hence this --transform option.
#              Also note that for some reason it doesn't work without excluding
#              .git directory. Excluding .tox is convenient for local builds.
tar -czvf ${source_path}/kuryr-kubernetes.tar.gz --exclude=.git --exclude=.tox --transform "flags=r;s|\.|kuryr-kubernetes-${version}|" .
cp kuryr.logrotate ${source_path}
cp kuryr-controller.service ${source_path}
cp openshift-kuryr.tmpfs ${source_path}
cp kuryr-cni.service ${source_path}

# NOTE(dulek): We use this to get python3-pbr package in here.
curl http://base-openstack-4-6.ocp.svc > /etc/yum.repos.d/base-openstack-4-6.repo

yum install -y python3-pbr python3-devel

rpmbuild -ba -D "_topdir `pwd`/_output" openshift-kuryr-kubernetes-rhel8.spec
createrepo _output/RPMS/noarch
