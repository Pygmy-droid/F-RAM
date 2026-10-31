FROM mcr.microsoft.com/devcontainers/python:3.11

WORKDIR /workspace
COPY . /workspace
RUN python -m pip install --upgrade pip && pip install -r requirements-min.txt
