FROM ubuntu:16.04

RUN  apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get -y install git make && \
  DEBIAN_FRONTEND=noninteractive apt-get -y install python python-stdeb python-pip libmysqlclient-dev libssl-dev libffi-dev libvirt-dev && \
  DEBIAN_FRONTEND=noninteractive pip install --upgrade pip && \
  DEBIAN_FRONTEND=noninteractive pip install --upgrade setuptools && \
  DEBIAN_FRONTEND=noninteractive apt-get -y install python-argcomplete python-jsonschema python-logutils python-mysqldb python-paramiko python-requests python-yaml python-bottle python-libvirt

