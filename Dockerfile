# 基于轻量级 Python 3.11-slim 构建极简镜像
FROM python:3.11-slim

# 设置上海时区与环境变量 (确保 NAS 定时任务按中国标准时间精准运行)
ENV TZ=Asia/Shanghai \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    DOCKER_MODE=1

# 安装基础时区数据
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && ln -fs /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo ${TZ} > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 仅安装无头调度运行必需的核心轻量依赖 (镜像精简至最小)
RUN pip install --no-cache-dir requests schedule

# 拷贝核心工程代码
COPY config.py fetcher.py processor.py llm_analyzer.py email_sender.py main.py settings.example.json ./

# 启动默认开启全天候定时轮询服务
CMD ["python", "main.py", "--cron"]
