FROM getcarrier/performance:base-latest

ARG DEBIAN_FRONTEND=noninteractive
ENV JMETER_VERSION=5.5

ENV lg_name perfmeter
ENV lg_id 1
ARG UNAME=carrier
ARG UID=1001
ARG GID=1001

# Install utilities
RUN add-apt-repository ppa:deadsnakes/ppa && apt-get update && \
    apt-get install -y --no-install-recommends bash git gfortran python3.7 python3.7-dev python3.7-distutils python3-apt && \
    wget https://bootstrap.pypa.io/get-pip.py && python3.7 get-pip.py && \
    ln -s /usr/bin/python3.7 /usr/local/bin/python3 && \
    ln -s /usr/bin/python3.7 /usr/local/bin/python && \
    python -m pip install --upgrade pip && \
    apt-get clean && \
    python -m pip install setuptools==40.6.2 && \
    python -m pip install 'common==0.1.2' 'configobj==5.0.6' 'redis==3.2.0' 'argparse==1.4.0'  && \
    rm -rf /tmp/*

RUN pip install git+https://github.com/carrier-io/perfreporter.git@thresholds

# Creating carrier user and making him sudoer
RUN groupadd -g $GID $UNAME
RUN useradd -m -u $UID -g $GID -s /bin/bash $UNAME
RUN echo "carrier    ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Installing Java Jolokia
RUN  mkdir /opt/java && cd /opt/java \
 && wget -O jolokia-jvm-1.6.0-agent.jar \
 http://search.maven.org/remotecontent?filepath=org/jolokia/jolokia-jvm/1.6.0/jolokia-jvm-1.6.0-agent.jar

# Installing Telegraf
RUN cd /tmp && wget https://dl.influxdata.com/telegraf/releases/telegraf_1.8.3-1_amd64.deb && \
    dpkg -i telegraf_1.8.3-1_amd64.deb
COPY telegraf.conf /etc/telegraf/telegraf.conf
COPY jolokia.conf /opt

RUN apt-get update && \
  apt-get install -qy \
  tzdata ca-certificates libsystemd-dev && \
  rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install JMeter
RUN mkdir /jmeter
RUN chown -R ${UNAME}:${UNAME} /jmeter
RUN chown -R ${UNAME}:${UNAME} /jmeter/
USER carrier
RUN   cd /jmeter/ \
      && wget https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-$JMETER_VERSION.tgz \
      && tar -xzf apache-jmeter-$JMETER_VERSION.tgz \
      && rm apache-jmeter-$JMETER_VERSION.tgz

# Set JMeter Home
ENV JMETER_HOME /jmeter/apache-jmeter-$JMETER_VERSION/

# Add JMeter to the Path
ENV PATH $JMETER_HOME/bin:$PATH

# Copy all necessary files to container image
COPY post_processing/ /
COPY pre_processing/ /
COPY launch.sh /
RUN sudo chmod +x /launch.sh
COPY Common/AddRemoveListener/ /
COPY Common/lib/ /jmeter/apache-jmeter-$JMETER_VERSION/lib
COPY Common/InfluxBackendListenerClient.jar /jmeter/apache-jmeter-$JMETER_VERSION/lib/ext
COPY Tests /mnt/jmeter
COPY config.yaml /tmp/
COPY reports /tmp/reports/

# Application to run on starting the container
ENTRYPOINT ["/launch.sh"]
