# Invoke with docker run -p 8000:80 <dockerimageid>
# Then use by browsing http://localhost:8000
FROM ubuntu:15.04
MAINTAINER bruno.cornec@hp.com
ENV DEBIAN_FRONTEND noninterative
# Install deps for Redfish mockup
RUN apt-get update
RUN apt-get -y install apache2 unzip sed
EXPOSE 80
COPY redfish-setup.sh /tmp/redfish-setup.sh
COPY DSP2043_0.96.0a.zip /tmp/DSP2043_0.96.0a.zip
RUN chmod 755 /tmp/redfish-setup.sh 
CMD /tmp/redfish-setup.sh
