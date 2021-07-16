FROM centos:centos8

COPY entrypoint.py /entrypoint.py
COPY requirements.txt /requirements.txt


RUN yum install -y python3 git
RUN pip3 install -r /requirements.txt

ENTRYPOINT ["/entrypoint.py"]
