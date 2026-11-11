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
"""Publishes rendered newsletter images to GCS and returns browser-loadable URLs.

A2UI ``Image`` components are fetched directly by the end user's browser (the
Gemini Enterprise web app), so every image needs an HTTPS URL that works without
Google Cloud credentials. Objects are written to a private bucket and exposed via
V4 signed URLs (max. 7 days), signed through the IAM ``signBlob`` API - no key
files involved.

Signer: ``NEWSLETTER_SIGNER_SA`` (a user-managed SA on which the runtime
identity holds ``roles/iam.serviceAccountTokenCreator``). This also works when
Agent Runtime runs as the Google-managed service agent, which cannot sign for
itself. Without it the runtime SA signs for itself.

Fallback order when signing is unavailable (e.g. local dev with user ADC):
  1. ``https://storage.googleapis.com/...`` if ``NEWSLETTER_ASSETS_PUBLIC=true``
  2. ``data:`` URI (works in ADK Web; GE may block it depending on CSP)
"""

from __future__ import annotations

import base64
import datetime
import functools
import hashlib
import os
import threading

import google.auth
from google.auth.transport.requests import Request

_SIGNED_URL_TTL = datetime.timedelta(days=7)
_lock = threading.Lock()


def _bucket_name() -> str | None:
    return (
        os.environ.get("NEWSLETTER_ASSETS_BUCKET")
        or os.environ.get("LOGS_BUCKET_NAME")
        or None
    )


@functools.cache
def _storage_client():
    from google.cloud import storage

    return storage.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"))


def _signing_credentials():
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    with _lock:
        if not creds.valid:
            creds.refresh(Request())
    sa_email = getattr(creds, "service_account_email", None)
    if not sa_email or sa_email == "default":
        # Metadata-server creds expose the real email only after a refresh.
        sa_email = getattr(creds, "_service_account_email", None) or sa_email
    return creds, sa_email


def _data_uri(data: bytes, mime_type: str) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}"


def publish_image(data: bytes, mime_type: str, prefix: str = "newsletter") -> str:
    """Uploads ``data`` and returns an HTTPS URL a browser can load."""
    bucket_name = _bucket_name()
    if not bucket_name:
        print("DEBUG: image_host: no bucket configured, using data URI")
        return _data_uri(data, mime_type)

    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(
        mime_type, "bin"
    )
    digest = hashlib.sha256(data).hexdigest()[:24]
    object_name = f"{prefix}/{digest}.{ext}"
    try:
        bucket = _storage_client().bucket(bucket_name)
        blob = bucket.blob(object_name)
        blob.cache_control = "public, max-age=604800, immutable"
        blob.upload_from_string(data, content_type=mime_type)
    except Exception as e:
        print(f"DEBUG: image_host: upload to gs://{bucket_name} failed: {e}")
        return _data_uri(data, mime_type)

    if os.environ.get("NEWSLETTER_ASSETS_PUBLIC", "").lower() in ("1", "true"):
        return f"https://storage.googleapis.com/{bucket_name}/{object_name}"

    try:
        creds, sa_email = _signing_credentials()
        sa_email = os.environ.get("NEWSLETTER_SIGNER_SA") or sa_email
        if not sa_email:
            raise RuntimeError("runtime credentials have no service account email")
        return blob.generate_signed_url(
            version="v4",
            expiration=_SIGNED_URL_TTL,
            method="GET",
            service_account_email=sa_email,
            access_token=creds.token,
        )
    except Exception as e:
        print(f"DEBUG: image_host: signing failed ({e}); using data URI")
        return _data_uri(data, mime_type)
