FROM centos:centos8

COPY entrypoint.py /entrypoint.py

RUN yum install -y python3 git
RUN pip3 install requests gitpython

ENTRYPOINT ["/entrypoint.py"]
