FROM flink:1.16-java11 as base

ENV FLINK_VERSION=1.16 \
    FLINK_MINOR_VERSION=1 \
    SCALA_VERSION=2.12 \
    ICEBERG_VERSION=1.1.0 \
    CDC_VERSION=2.3.0 \
    HMS_VERSION=3.1.2 \
    HADOOP_VERSION=3.2.1

RUN set -xe

# Install python
RUN apt-get update -y && \
    apt-get install -y build-essential libssl-dev zlib1g-dev libbz2-dev libffi-dev liblzma-dev && \
    wget https://www.python.org/ftp/python/3.9.16/Python-3.9.16.tgz && \
    tar -xvf Python-3.9.16.tgz && \
    cd Python-3.9.16 && \
    ./configure --without-tests --enable-shared && \
    make -j6 && \
    make install && \
    ldconfig /usr/local/lib && \
    cd .. && rm -f Python-3.9.16.tgz && rm -rf Python-3.9.16 && \
    ln -s /usr/local/bin/python3 /usr/local/bin/python && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN wget -P ${FLINK_HOME}/lib https://repo1.maven.org/maven2/com/ververica/flink-sql-connector-postgres-cdc/${CDC_VERSION}/flink-sql-connector-postgres-cdc-${CDC_VERSION}.jar \
    && wget -P ${FLINK_HOME}/lib https://repo1.maven.org/maven2/commons-cli/commons-cli/1.5.0/commons-cli-1.5.0.jar

COPY ./requirements.txt .

RUN pip3 install \
      --disable-pip-version-check \
      --no-cache-dir \
      --no-compile \
      --upgrade poetry \
      -r requirements.txt

COPY src ./src
