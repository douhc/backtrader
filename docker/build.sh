#!/bin/bash

VERSION=v1.0.0
REPO_SERVER=hub.docker.com
IMAGE_NAME=backtrader:${VERSION}
REMOTE_IMAGE_NAME=${REPO_SERVER}/repository/docker/douhongchen/${IMAGE_NAME}

docker build -t $IMAGE_NAME  -f Dockerfile ..
# docker push ${REMOTE_IMAGE_NAME}