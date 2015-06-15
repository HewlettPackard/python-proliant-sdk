%global srcname redfish

Name:           python-%{srcname}
Version:        0.1
Release:        %mkrel 1
Summary:        Redfish python library

Group:          Development/Python
License:        Apache v2.0
URL:            https://github.com/devananda/python-redfish
Source0:        %name-%version.tar.gz

BuildArch:      noarch
BuildRequires:  python-devel
BuildRequires:  python-setuptools

%description
The Redfish API supports dialoging with a Redfish compliant 
system such as defined by http://www.redfishcertification.org

%prep
%setup -q -n %{name}
#-%{version}

%build
%{__python} setup.py build

%install
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

%files
%dir %{python_sitelib}/redfish
%{python_sitelib}/redfish/*
%{python_sitelib}/python_redfish*
