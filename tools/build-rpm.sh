#!/bin/bash -x

code_path=/kuryr-kubernetes-0.6.1
source_path=$HOME/rpmbuild/SOURCES

cp -r /go/src/github.com/openshift/kuryr-kubernetes ${code_path}

mkdir -p ${source_path}
tar -czvf ${source_path}/kuryr-kubernetes-0.6.1.tar.gz --exclude=.git ${code_path}
cp ${code_path}/kuryr.logrotate ${source_path}
cp ${code_path}/kuryr-controller.service ${source_path}
cp ${code_path}/openshift-kuryr.tmpfs ${source_path}
cp ${code_path}/kuryr-cni.service ${source_path}

# FIXME(dulek): Don't use hardcoded tarball name.
#sed -i -e 's/Source0.*/Source0   openshift-kuryr.tar.gz/g' $code_path/openshift-kuryr-kubernetes.spec
#sed -i '/Source[1-9]/d' $code_path/openshift-kuryr-kubernetes.spec

# FIXME(dulek): For some reason python2-pbr is not available in CI ecosystem.
#               I'm injecting it from the repo, but need to fix this.
yum install -y ${code_path}/python2-pbr-3.1.1-3.el7ar.noarch.rpm python-devel
rpmbuild -ba ${code_path}/openshift-kuryr-kubernetes.spec
