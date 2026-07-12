#!/usr/bin/env bash
# Deploys the app to Cloud Run.
#
# --no-cpu-throttling is not optional: the agent pipelines run in a background
# thread after the HTTP response returns, and Cloud Run only allocates CPU
# during active request handling by default. Without this flag the pipeline
# stalls between polls instead of progressing — this was a real bug hit
# during development, not a hypothetical, so it's codified here instead of
# left as something to remember on the next deploy.
#
# PUBLIC_BASE_URL matters for the authenticity layer specifically: it's baked
# into every QR code as the verification URL. Get it wrong and every QR issued
# points at the wrong place. Defaults to this service's known Cloud Run URL —
# override via env var if you're deploying a fork under a different URL.
set -euo pipefail

PROJECT="${GCP_PROJECT:?Set GCP_PROJECT, e.g. export GCP_PROJECT=gowthamaccount}"
REGION="${GCP_REGION:-asia-south1}"
SERVICE="${SERVICE_NAME:-sebi-synthetic-media-detector}"
GEMINI_SECRET="${GEMINI_SECRET_NAME:-sebi-synthetic-media-gemini-key}"
SIGNING_SECRET="${SIGNING_SECRET_NAME:-sebi-synthetic-media-signing-key}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-https://sebi-synthetic-media-detector-564262191703.asia-south1.run.app}"
ACCOUNT_FLAG=()
[ -n "${GCP_ACCOUNT:-}" ] && ACCOUNT_FLAG=(--account "$GCP_ACCOUNT")

cd "$(dirname "$0")"

gcloud run deploy "$SERVICE" \
  --source . \
  --project "$PROJECT" \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --no-cpu-throttling \
  --set-env-vars "PUBLIC_BASE_URL=${PUBLIC_BASE_URL}" \
  --set-secrets "GEMINI_API_KEY=${GEMINI_SECRET}:latest,SIGNING_PRIVATE_KEY_PEM=${SIGNING_SECRET}:latest" \
  "${ACCOUNT_FLAG[@]}"

echo
echo "Deployed. Verify the CPU-throttling flag actually stuck:"
echo "  gcloud run services describe $SERVICE --region $REGION --project $PROJECT \\"
echo "    --format='value(spec.template.metadata.annotations[\"run.googleapis.com/cpu-throttling\"])'"
echo "(should print 'false' — if it prints nothing/true, the flag was dropped)"
