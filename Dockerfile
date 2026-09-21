FROM python:3.12-slim
WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends unzip && rm -rf /var/lib/apt/lists/*
COPY show_me_claim_tool_deploy/show_me_claim_tool.zip /srv/show_me_claim_tool.zip
RUN unzip /srv/show_me_claim_tool.zip -d /srv && pip install --no-cache-dir -r /srv/show_me_claim_tool/requirements.txt
WORKDIR /srv/show_me_claim_tool
ENV PORT=8080
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:$PORT app:app"]
