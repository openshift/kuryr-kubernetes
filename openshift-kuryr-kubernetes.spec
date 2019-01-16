%{!?upstream_version: %global upstream_version %{version}%{?milestone}}
%global project kuryr
%global service kuryr-kubernetes
%global module kuryr_kubernetes

%global common_desc \
Kuryr Kubernetes provides a Controller that watches the Kubernetes API for \
Object changes and manages Neutron resources to provide the Kubernetes Cluster \
with OpenStack networking.

Name:      openshift-%service
Version:   0.6.1
Release:   1%{?dist}
Summary:   OpenStack networking integration with OpenShift and Kubernetes
License:   ASL 2.0
URL:       http://docs.openstack.org/developer/kuryr-kubernetes/

Source0:   %{service}-%{upstream_version}.tar.gz
Source1:   kuryr.logrotate
Source2:   kuryr-controller.service
Source3:   openshift-kuryr.tmpfs
Source4:   kuryr-cni.service

BuildArch: noarch

Requires(pre): shadow-utils
%{?systemd_requires}

%description
Kuryr-Kubernetes brings OpenStack networking to OpenShift and Kubernetes clusters

%package -n python2-%{service}
Summary:        Kuryr Kubernetes libraries
%{?python_provide:%python_provide python2-%{service}}

BuildRequires:  git
BuildRequires:  python2-devel
BuildRequires:  python2-setuptools
BuildRequires:  python2-pbr
BuildRequires:  systemd-units

Requires:       python2-%{project}-lib >= 0.5.0
Requires:       python2-pyroute2 >= 0.4.21
Requires:       python2-requests >= 2.14.2
Requires:       python2-eventlet >= 0.18.2
Requires:       python2-oslo-cache >= 1.26.0
Requires:       python2-oslo-config >= 2:5.2.0
Requires:       python2-oslo-log >= 3.36.0
Requires:       python2-oslo-reports >= 1.18.0
Requires:       python2-oslo-serialization >= 2.18.0
Requires:       python2-oslo-service >= 1.24.0
Requires:       python2-oslo-utils >= 3.33.0
Requires:       python2-os-vif >= 1.7.0
Requires:       python2-six >= 1.10.0
Requires:       python2-stevedore >= 1.20.0
Requires:       python2-cotyledon >= 1.3.0
Requires:       python-flask >= 0.10.0
Requires:       python-retrying >= 1.2.3

%description -n python2-%{service}
%{common_desc}

This package contains the Kuryr Kubernetes Python library.

%package common
Summary:        Kuryr Kubernetes common files
Group:          Applications/System
Requires:   python2-%{service} = %{version}-%{release}

%description common
This package contains Kuryr files common to all services.

%package controller
Summary: Kuryr Kubernetes Controller
Requires: openshift-%{service}-common = %{version}-%{release}

%description controller
%{common_desc}

This package contains the Kuryr Kubernetes Controller that watches the
Kubernetes API and adds metadata to its Objects about the OpenStack resources
it obtains.

%package cni
Summary: CNI plugin
Requires: openshift-%{service}-common = %{version}-%{release}
%{?systemd_requires}

%description cni
%{common_desc}

This package contains the Kuryr Kubernetes Container Network Interface driver
that Kubelet calls to.

%prep
%autosetup -n %{service}-%{upstream_version} -S git

find %{module} -name \*.py -exec sed -i '/\/usr\/bin\/env python/{d;q}' {} +

# Let's handle dependencies ourseleves
rm -f requirements.txt
rm -f test-requirements.txt
rm -f doc/requirements.txt

# Kill egg-info in order to generate new SOURCES.txt
rm -rf kuryr_kubernetes.egg-info

%build
%py2_build

%install
%py2_install

# Create config files directories
install -d -m 755 %{buildroot}%{_sysconfdir}/%{project}
install -d -m 755 %{buildroot}%{_localstatedir}/log/%{project}

# Install logrotate
install -p -D -m 644 %{SOURCE1} %{buildroot}%{_sysconfdir}/logrotate.d/openshift-%{service}

# Install systemd units
install -p -D -m 644 %{SOURCE2} %{buildroot}%{_unitdir}/kuryr-controller.service
install -p -D -m 644 %{SOURCE4} %{buildroot}%{_unitdir}/kuryr-cni.service

# Kuryr run directories
install -p -D -m 644 %{SOURCE3} %{buildroot}%{_tmpfilesdir}/openshift-kuryr.conf
install -d %{buildroot}%{_localstatedir}/run/kuryr

# Kuryr cni_ds_init
install -d -m 755 %{buildroot}%{_libexecdir}/%{project}
install -p -D -m 755 cni_ds_init %{buildroot}%{_libexecdir}/%{project}/
install -p -D -m 755 etc/cni/net.d/10-kuryr.conf %{buildroot}%{_sysconfdir}/%{project}-cni/10-kuryr.conf

%pre -n python2-%{service}
getent group %{project} >/dev/null || groupadd -r %{project}
getent passwd %{project} >/dev/null || \
    useradd -r -g %{project} -d %{_sharedstatedir}/%{project} -s /sbin/nologin \
    -c "OpenStack Kuryr Daemons" %{project}
exit 0

%post controller
%systemd_post kuryr-controller.service

%preun controller
%systemd_preun kuryr-controller.service

%postun controller
%systemd_postun_with_restart kuryr-controller.service

%post cni
%systemd_post kuryr-cni.service

%preun cni
%systemd_preun kuryr-cni.service

%postun cni
%systemd_postun_with_restart kuryr-cni.service

%files controller
%license LICENSE
%{_bindir}/kuryr-k8s-controller
%{_bindir}/kuryr-k8s-status
%{_unitdir}/kuryr-controller.service

%files -n python2-%{service}
%license LICENSE
%{python2_sitelib}/%{module}
%{python2_sitelib}/%{module}-*.egg-info
%exclude %{python2_sitelib}/%{module}/tests

%files common
%license LICENSE
%doc README.rst
%dir %attr(0755, %{project}, %{project}) %{_sysconfdir}/%{project}
%config(noreplace) %{_sysconfdir}/logrotate.d/*
%dir %attr(0755, %{project}, %{project}) %{_localstatedir}/log/%{project}
%{_tmpfilesdir}/openshift-kuryr.conf
%dir %attr(0755, %{project}, %{project}) %{_localstatedir}/run/kuryr

%files cni
%license LICENSE
%{_bindir}/kuryr-cni
%{_bindir}/kuryr-daemon
%{_unitdir}/kuryr-cni.service
%dir %attr(0755, root, root) %{_libexecdir}/%{project}
%{_libexecdir}/%{project}/cni_ds_init
%config(noreplace) %attr(0640, root, %{project}) %{_sysconfdir}/%{project}-cni/10-kuryr.conf
