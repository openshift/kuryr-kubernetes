#!/bin/bash -x

code_path=/kuryr-kubernetes-0.6.1
source_path=$HOME/rpmbuild/SOURCES
mkdir -p ${source_path}
tar -czvf ${source_path}/kuryr-kubernetes-0.6.1.tar.gz ${code_path}
cp ${code_path}/kuryr.logrotate ${source_path}
cp ${code_path}/kuryr-controller.service ${source_path}
cp ${code_path}/openshift-kuryr.tmpfs ${source_path}
cp ${code_path}/kuryr-cni.service ${source_path}

# FIXME(dulek): Don't use hardcoded tarball name.
#sed -i -e 's/Source0.*/Source0   openshift-kuryr.tar.gz/g' $code_path/openshift-kuryr-kubernetes.spec
#sed -i '/Source[1-9]/d' $code_path/openshift-kuryr-kubernetes.spec

rpmbuild -ba ${code_path}/openshift-kuryr-kubernetes.spec

yum install ${HOME}/rpmbuild/RPMS/python2-kuryr-kubernetes-0.6.1-1.el7.noarch.rpm
yum install ${HOME}/rpmbuild/RPMS/openshift-kuryr-kubernetes-common-0.6.1-1.el7.noarch.rpm
if [[ $1 == "controller" ]]; then
    yum install ${HOME}/rpmbuild/RPMS/openshift-kuryr-kubernetes-controller-0.6.1-1.el7.noarch.rpm
elif [[ $1 == "cni" ]]; then
    yum install ${HOME}/rpmbuild/RPMS/openshift-kuryr-kubernetes-cni-0.6.1-1.el7.noarch.rpm
fi
