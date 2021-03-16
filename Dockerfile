FROM tiangolo/uvicorn-gunicorn-fastapi:python3.7

ARG S3BUCKET
ARG S3MODELPATH
ARG S3SCHEMAPATH
ENV AWS_DEFAULT_REGION=us-east-1
ARG AWS_SECRET_ACCESS_KEY
ARG AWS_ACCESS_KEY_ID

RUN mkdir -p /usr/src/app
RUN mkdir -p /usr/src/app/models

WORKDIR /usr/src/app

RUN apt update -y && \
    apt install default-jdk -y && \
    wget https://oss.sonatype.org/content/repositories/releases/io/swagger/swagger-codegen-cli/2.2.1/swagger-codegen-cli-2.2.1.jar

COPY requirements.txt /usr/src/app/
COPY swagger-codegen /bin/

RUN chmod +x /bin/swagger-codegen
RUN pip3 install -r requirements.txt

COPY . /usr/src/app

RUN aws s3 cp s3://${S3BUCKET}/${S3SCHEMAPATH} ./ && \
    aws s3 cp s3://${S3BUCKET}/${S3MODELPATH} ./ && \
    python generate.py unzip

CMD ["uvicorn", "app:app",  "--host", "0.0.0.0"]
