FROM centos:7

# install epel
RUN yum install -y wget
RUN yum install -y epel-release
#RUN wget http://dl.fedoraproject.org/pub/epel/7/x86_64/e/epel-release-7-10.noarch.rpm && rpm -ivh epel-release-7-10.noarch.rpm

# install jq
RUN yum install -y jq

COPY run.sh /

CMD bash /run.sh

