FROM python:3.11-slim

RUN python -m pip install --no-cache-dir "kiss-icp==1.3.0" "PyYAML>=6,<7"

COPY runner.py /opt/lidarperf/runner.py
ENTRYPOINT ["python", "/opt/lidarperf/runner.py"]
