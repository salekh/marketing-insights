#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Redeploys the REWE agent to Agent Runtime with the A2UI newsletter for
# Gemini Enterprise, and provisions what the widget needs at runtime:
#   * a private GCS bucket for the rendered newsletter images,
#   * a signer SA so the runtime identity can mint V4 signed image URLs
#     (works even when Agent Runtime runs as the Google-managed service agent).
#
# Usage:  deployment/deploy_ge_a2ui.sh            (idempotent, safe to re-run)
# Prereq: gcloud auth login && gcloud auth application-default login
#         for the account behind the gcloud configuration below.
set -euo pipefail

export CLOUDSDK_ACTIVE_CONFIG_NAME="${GCLOUD_CONFIGURATION:-argolis-project}"
PROJECT="${PROJECT:-sa-learning-1}"
REGION="${REGION:-us-east1}"
BUCKET="${NEWSLETTER_ASSETS_BUCKET:-${PROJECT}-rewe-newsletter-assets}"
SIGNER_NAME="${SIGNER_NAME:-rewe-newsletter-signer}"
SIGNER="${SIGNER_NAME}@${PROJECT}.iam.gserviceaccount.com"
A2UI_VERSION="${A2UI_VERSION:-v0.9}"

cd "$(dirname "$0")/.."

# IAM is eventually consistent (fresh SAs take ~1 min to become bindable).
retry() {
  local n=0
  until "$@"; do
    n=$((n + 1))
    if ((n >= 12)); then return 1; fi
    echo "   ...retrying in 10s ($n/12)"
    sleep 10
  done
}

echo "== gcloud config: ${CLOUDSDK_ACTIVE_CONFIG_NAME} / project ${PROJECT}"
gcloud auth print-access-token >/dev/null
gcloud auth application-default print-access-token >/dev/null
PROJECT_NUMBER="$(gcloud projects describe "${PROJECT}" --format='value(projectNumber)')"

ENGINE="$(python3 -c "import json;print(json.load(open('deployment_metadata.json')).get('remote_agent_runtime_id',''))")"
RUNTIME_SA=""
if [[ -n "${ENGINE}" ]]; then
  RUNTIME_SA="$(curl -fsS -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    "https://${REGION}-aiplatform.googleapis.com/v1beta1/${ENGINE}" |
    python3 -c 'import json,sys;print(json.load(sys.stdin).get("spec",{}).get("serviceAccount",""))' || true)"
fi
RUNTIME_SA="${RUNTIME_SA:-service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com}"
echo "== Agent Runtime identity: ${RUNTIME_SA}"

echo "== Bucket gs://${BUCKET}"
gcloud storage buckets describe "gs://${BUCKET}" >/dev/null 2>&1 ||
  gcloud storage buckets create "gs://${BUCKET}" --project "${PROJECT}" \
    --location "${REGION}" --uniform-bucket-level-access \
    --public-access-prevention
retry gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member "serviceAccount:${RUNTIME_SA}" --role roles/storage.objectAdmin >/dev/null

echo "== Signer ${SIGNER}"
gcloud iam service-accounts describe "${SIGNER}" --project "${PROJECT}" >/dev/null 2>&1 ||
  gcloud iam service-accounts create "${SIGNER_NAME}" --project "${PROJECT}" \
    --display-name "REWE newsletter image URL signer"
# Signed URLs carry the signer's permissions -> read-only on this bucket only.
retry gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member "serviceAccount:${SIGNER}" --role roles/storage.objectViewer >/dev/null
retry gcloud iam service-accounts add-iam-policy-binding "${SIGNER}" --project "${PROJECT}" \
  --member "serviceAccount:${RUNTIME_SA}" \
  --role roles/iam.serviceAccountTokenCreator >/dev/null

echo "== Tests"
uv run pytest tests/unit -q -p no:cacheprovider -W ignore::DeprecationWarning

echo "== Deploy (Agent Runtime, ${REGION})"
agents-cli deploy --project "${PROJECT}" --region "${REGION}" --no-confirm-project \
  --update-env-vars "A2UI_VERSION=${A2UI_VERSION},NEWSLETTER_ASSETS_BUCKET=${BUCKET},NEWSLETTER_SIGNER_SA=${SIGNER}"

echo "== Done. Engine: $(python3 -c "import json;print(json.load(open('deployment_metadata.json'))['remote_agent_runtime_id'])")"
