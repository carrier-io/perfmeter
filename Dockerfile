# 1 Use Java 8 slim JRE
FROM openjdk:8-jre-slim

# 2 JMeter version passed via command line argument (docker build --build-arg JMETER_VERSION=5.0 -t jmeter -f Dockerfile  .)
ARG JMETER_VERSION=5.0

ENV lg_name perfmeter
ENV lg_id 1
ARG UNAME=carrier
ARG UID=1001
ARG GID=1001

# 3 Install utilities
RUN apt-get update && \
    apt-get install -y --no-install-recommends bash sudo git wget python python-dev python-pip && \
    python -m pip install --upgrade pip && \
    apt-get clean && \
    python -m pip install 'numpy==1.16.0' 'influxdb==5.2.0' 'argparse==1.4.0' && \
    rm -rf /tmp/*

# 4 Creating carrier user and making him sudoer
RUN groupadd -g $GID $UNAME
RUN useradd -m -u $UID -g $GID -s /bin/bash $UNAME
RUN echo "carrier    ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# 5 Install JMeter
RUN mkdir /jmeter
RUN chown -R ${UNAME}:${UNAME} /jmeter
RUN chown -R ${UNAME}:${UNAME} /jmeter/
USER carrier
RUN   cd /jmeter/ \
      && wget https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-$JMETER_VERSION.tgz \
      && tar -xzf apache-jmeter-$JMETER_VERSION.tgz \
      && rm apache-jmeter-$JMETER_VERSION.tgz

# 6 Set JMeter Home
ENV JMETER_HOME /jmeter/apache-jmeter-$JMETER_VERSION/

# 7 Add JMeter to the Path
ENV PATH $JMETER_HOME/bin:$PATH

# 8 Copy all necessary files to container image
COPY Common/launch.sh /
RUN sudo chmod +x /launch.sh
COPY Common/AddRemoveListener/ /
COPY Common/lib/ /jmeter/apache-jmeter-$JMETER_VERSION/lib
COPY Common/InfluxBackendListenerClient.jar /jmeter/apache-jmeter-$JMETER_VERSION/lib/ext
COPY Tests /mnt/jmeter
RUN sudo chmod -R 777 /mnt/jmeter
RUN sudo chmod -R 777 /jmeter

# 9 Application to run on starting the container
ENTRYPOINT ["/launch.sh"]
