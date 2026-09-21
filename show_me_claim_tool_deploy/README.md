# SHOW ME Claim Tool — Railway deployment wrapper

Railway root directory: `/show_me_claim_tool_deploy`

Required environment variables:
- `SHOWME_CLASS_CODE`
- `SHOWME_ADMIN_KEY`
- `SHOWME_SECRET_KEY`
- `SHOWME_DB_PATH=/data/showme.db`

Mount a persistent Railway volume at `/data`.

The Dockerfile unpacks `show_me_claim_tool.zip`, installs dependencies, and starts the Flask app with gunicorn.
