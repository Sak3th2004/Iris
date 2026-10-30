FROM mcr.microsoft.com/playwright/python:v1.64.1-noble
USER root
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends xfce4-session xfwm4 xfce4-panel xfdesktop4 dbus-x11 x11vnc xdotool x11-utils fonts-inter && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir playwright==1.64.1 httpx==0.28.1
WORKDIR /worker
COPY worker/desktop_worker.py run.py
COPY worker/start-desktop.sh /worker/start-desktop.sh
RUN chmod +x /worker/start-desktop.sh && mkdir -p /home/pwuser/iris-profile && chown -R pwuser:pwuser /home/pwuser/iris-profile
USER pwuser
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
CMD ["/worker/start-desktop.sh"]
