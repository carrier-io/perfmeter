# 1 Use Java 8 slim JRE
FROM openjdk:8-jdk

# 2 JMeter version passed via command line argument (docker build --build-arg JMETER_VERSION=5.0 -t jmeter -f Dockerfile  .)
ARG JMETER_VERSION=5.0

ENV lg_name perfmeter
ENV lg_id 1
ARG UNAME=carrier
ARG UID=1001
ARG GID=1001

COPY rp_client_3.2.zip /tmp

# 3 Install utilities
RUN apt-get update && \
    apt-get install -y --no-install-recommends bash sudo git wget python python-dev python-pip && \
    python -m pip install --upgrade pip && \
    apt-get clean && \
    python -m pip install setuptools==40.6.2 && \
    python -m pip install /tmp/rp_client_3.2.zip 'numpy==1.16.0' 'PyYAML==3.13' 'jira==2.0.0' 'influxdb==5.2.0' 'argparse==1.4.0' 'requests==2.19.1' && \
    rm -rf /tmp/*

# 4 Creating carrier user and making him sudoer
RUN groupadd -g $GID $UNAME
RUN useradd -m -u $UID -g $GID -s /bin/bash $UNAME
RUN echo "carrier    ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# 5 Installing Java Jolokia
RUN  mkdir /opt/java && cd /opt/java \
 && wget -O jolokia-jvm-1.6.0-agent.jar \
 http://search.maven.org/remotecontent?filepath=org/jolokia/jolokia-jvm/1.6.0/jolokia-jvm-1.6.0-agent.jar

# 6 Installing Telegraf
RUN cd /tmp && wget https://dl.influxdata.com/telegraf/releases/telegraf_1.8.3-1_amd64.deb && \
    dpkg -i telegraf_1.8.3-1_amd64.deb
COPY telegraf.conf /etc/telegraf/telegraf.conf
COPY jolokia.conf /opt

# 7 Install JMeter
RUN mkdir /jmeter
RUN chown -R ${UNAME}:${UNAME} /jmeter
RUN chown -R ${UNAME}:${UNAME} /jmeter/
USER carrier
RUN   cd /jmeter/ \
      && wget https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-$JMETER_VERSION.tgz \
      && tar -xzf apache-jmeter-$JMETER_VERSION.tgz \
      && rm apache-jmeter-$JMETER_VERSION.tgz

# 8 Set JMeter Home
ENV JMETER_HOME /jmeter/apache-jmeter-$JMETER_VERSION/

# 9 Add JMeter to the Path
ENV PATH $JMETER_HOME/bin:$PATH

# 10 Copy all necessary files to container image
COPY Common/launch.sh /
RUN sudo chmod +x /launch.sh
COPY Common/AddRemoveListener/ /
COPY Common/lib/ /jmeter/apache-jmeter-$JMETER_VERSION/lib
COPY Common/InfluxBackendListenerClient.jar /jmeter/apache-jmeter-$JMETER_VERSION/lib/ext
COPY Tests /mnt/jmeter
COPY config.yaml /tmp/

# 11 Application to run on starting the container
ENTRYPOINT ["/launch.sh"]
