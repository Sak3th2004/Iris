FROM mcr.microsoft.com/playwright/python:v1.64.1-noble
RUN pip install --no-cache-dir playwright==1.64.1 httpx==0.28.1
WORKDIR /worker
COPY worker/desktop_worker.py run.py
USER pwuser
ENV PYTHONUNBUFFERED=1
CMD ["xvfb-run", "-a", "python", "run.py"]
