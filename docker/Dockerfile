FROM ubuntu:20.04

## 修改APT源
RUN cp -r /etc/apt/sources.list /etc/apt/sources.list.bk
COPY docker/sources.list /etc/apt/sources.list

ENV LANG=en_US.UTF-8 \
        LC_ALL=en_US.UTF-8 \
        TZ=Asia/Shanghai

ENV DEBIAN_FRONTEND=noninteractive

RUN set -ex && \
        apt-get -y update && \
        apt-get install -y ca-certificates apt-transport-https tzdata && \
        apt-get install -y build-essential && \
        apt-get install -y curl bzip2 tar wget grep sed dpkg telnet vim zip unzip rsync git cmake && \
        apt-get install -y locales && localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8 && \
        apt-get install -y python3-distutils python3-dev pkg-config python3-pip libcrypto++ && \
        update-alternatives --install /usr/bin/python python /usr/bin/python3 1 && \
        update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1 && \
        apt-get clean && rm -rf /var/lib/apt/lists/*

RUN mkdir /root/.pip
COPY docker/pip.conf /root/.pip/pip.conf
#####################################
RUN mkdir -p /data /opt/backtrader

ADD requirements.txt /root/
RUN pip3 install -r /root/requirements.txt && \
    rm -rf /root/.cache/pip

ENTRYPOINT [ "bash" ]
