FROM python:3.12-slim
WORKDIR /app
COPY show_me_claim_tool_deploy/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY show_me_claim_tool_deploy/app.py .
ENV PORT=8080
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:$PORT app:app"]
