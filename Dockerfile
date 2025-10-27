FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.2

# -- зависимости системы --
RUN apt-get update && apt-get install -y \
    ffmpeg build-essential curl && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/avatar

COPY pyproject.toml poetry.lock ./
RUN pip install "poetry==$POETRY_VERSION" && poetry config virtualenvs.create false \
    && poetry install --no-dev --without test

COPY app ./app
COPY utils ./utils

# Entrypoint определяется в docker-compose; так удобнее




# # 使用 NVIDIA CUDA 镜像（Ubuntu 20.04 + CUDA 11.8 + cuDNN 8）
# FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu20.04
#
# # 设置非交互式环境变量
# ENV DEBIAN_FRONTEND=noninteractive
#
# # 复制公司 CA 证书到容器，并更新 CA 存储
# # 请确保你已将 Unified_State_Internet_Access_Gateway.crt 放在 Docker 构建上下文中（与 Dockerfile 同一目录）
# COPY Unified_State_Internet_Access_Gateway.crt /usr/local/share/ca-certificates/
# RUN update-ca-certificates
#
# # （可选）设置环境变量给 pip 使用系统 CA 存储
# ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
# ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
#
# # 安装系统依赖
# RUN apt-get update && apt-get install -y \
#     ffmpeg \
#     git \
#     curl \
#     wget \
#     libgl1 \
#     python3-pip \
#     && apt-get clean && rm -rf /var/lib/apt/lists/*
#
# WORKDIR /app
#
# # 复制项目文件
# COPY . .
#
# # 升级 pip
# RUN pip3 install --upgrade pip
#
# # 预先安装 PyTorch 及相关库（注意使用与你网络环境匹配且可用的版本）
# RUN pip install torch==2.4.1+cu118 torchvision==0.19.1+cu118 torchaudio==2.4.1+cu118 --extra-index-url https://download.pytorch.org/whl/cu118
#
# # 安装其余依赖
# RUN pip install --prefer-binary -r requirements.txt
#
# # 暴露端口（根据你的项目需要修改）
# EXPOSE 5000
#
# # 默认启动命令（根据实际情况修改）
# CMD ["python3", "app.py"]
