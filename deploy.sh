#!/usr/bin/env bash
# Deploys the Synthetic Media Fraud Detector to Cloud Run.
#
# --no-cpu-throttling is not optional: the agent pipeline runs in a background
# thread after the HTTP response returns, and Cloud Run only allocates CPU
# during active request handling by default. Without this flag the pipeline
# stalls between polls instead of progressing — this was a real bug hit
# during development, not a hypothetical, so it's codified here instead of
# left as something to remember on the next deploy.
set -euo pipefail

PROJECT="${GCP_PROJECT:?Set GCP_PROJECT, e.g. export GCP_PROJECT=gowthamaccount}"
REGION="${GCP_REGION:-asia-south1}"
SERVICE="${SERVICE_NAME:-sebi-synthetic-media-detector}"
SECRET_NAME="${GEMINI_SECRET_NAME:-sebi-synthetic-media-gemini-key}"
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
  --set-secrets "GEMINI_API_KEY=${SECRET_NAME}:latest" \
  "${ACCOUNT_FLAG[@]}"

echo
echo "Deployed. Verify the CPU-throttling flag actually stuck:"
echo "  gcloud run services describe $SERVICE --region $REGION --project $PROJECT \\"
echo "    --format='value(spec.template.metadata.annotations[\"run.googleapis.com/cpu-throttling\"])'"
echo "(should print 'false' — if it prints nothing/true, the flag was dropped)"
