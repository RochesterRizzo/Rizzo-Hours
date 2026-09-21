# SHOW ME Claim Tool — Railway deployment

Railway root directory: `/show_me_claim_tool_deploy`

Required environment variables:
- `SHOWME_CLASS_CODE`
- `SHOWME_ADMIN_KEY`
- `SHOWME_SECRET_KEY`
- `SHOWME_DB_PATH=/data/showme.db`

Mount a persistent Railway volume at `/data`.

The Dockerfile now builds directly from the unpacked source in `app/`; no ZIP archive is required.
