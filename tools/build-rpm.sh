#!/bin/bash -x


code_path=/go/src/github.com/openshift/kuryr-kubernetes
mkdir -p $HOME/rpmbuild/SOURCES
cd $code_path
tar -czvf $HOME/rpmbuild/SOURCES/kuryr-kubernetes-0.6.1.tar.gz .
cd -

#sed -i -e 's/Source0.*/Source0   openshift-kuryr.tar.gz/g' $code_path/openshift-kuryr-kubernetes.spec
#sed -i '/Source[1-9]/d' $code_path/openshift-kuryr-kubernetes.spec

rpmbuild -ba $code_path/openshift-kuryr-kubernetes.spec
