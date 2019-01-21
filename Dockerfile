# 1 Use Java 8 slim JRE
FROM openjdk:8-jre-slim

# 2 JMeter version passed via command line argument (docker build --build-arg JMETER_VERSION=5.0 -t jmeter -f Dockerfile  .)
ARG JMETER_VERSION=5.0

# 3 Install utilities
RUN apt-get clean && \
    apt-get update && \
    apt-get -qy install \
                wget \
                git \
                python             

# 4 Cloning necessary files from repository
RUN git clone --single-branch --branch master https://github.com/carrier-io/perfmeter.git

# 5 Install JMeter
RUN   mkdir /jmeter \
      && cd /jmeter/ \      
      && wget https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-$JMETER_VERSION.tgz \
      && tar -xzf apache-jmeter-$JMETER_VERSION.tgz \
      && rm apache-jmeter-$JMETER_VERSION.tgz

# 6 Set JMeter Home
ENV JMETER_HOME /jmeter/apache-jmeter-$JMETER_VERSION/

# 7 Add JMeter to the Path
ENV PATH $JMETER_HOME/bin:$PATH

# 8 Copy all necessary files to container image
RUN mv /perfmeter/Common/launch.sh /
RUN mv /perfmeter/Common/AddRemoveListener/* /
RUN mkdir /mnt/jmeter
RUN mv /perfmeter/Tests/* /mnt/jmeter/
RUN rm -rf /jmeter/apache-jmeter-$JMETER_VERSION/lib/*
RUN mv /perfmeter/Common/lib/* /jmeter/apache-jmeter-$JMETER_VERSION/lib
RUN mv /perfmeter/Common/InfluxBackendListenerClient.jar /jmeter/apache-jmeter-$JMETER_VERSION/lib/ext


# 8 Application to run on starting the container
ENTRYPOINT ["/launch.sh"]