"""
Supabase Storage backend for Django.

Uploads all media files (worker docs, course files, verifications) to a
Supabase Storage bucket.  Works transparently with Django's FileField /
ImageField via DEFAULT_FILE_STORAGE.

Required environment variables
-------------------------------
SUPABASE_URL          – e.g. https://<project-ref>.supabase.co
SUPABASE_SERVICE_KEY  – Service-role secret key (NOT the anon key)
SUPABASE_BUCKET       – Name of the bucket, e.g. "saikona-media"
"""

import os
import mimetypes
from io import BytesIO

from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class SupabaseStorage(Storage):
    """Django Storage backend backed by a Supabase Storage bucket."""

    def __init__(self):
        from supabase import create_client, Client  # lazy import

        url: str = os.environ["SUPABASE_URL"]
        key: str = os.environ["SUPABASE_SERVICE_KEY"]
        self.bucket: str = os.environ.get("SUPABASE_BUCKET", "saikona-media")
        self.client: Client = create_client(url, key)
        self.public_url_base = f"{url}/storage/v1/object/public/{self.bucket}"

    # ------------------------------------------------------------------
    # Core Storage API
    # ------------------------------------------------------------------

    def _open(self, name, mode="rb"):
        """Return file-like object for reading."""
        data = self.client.storage.from_(self.bucket).download(name)
        return BytesIO(data)

    def _save(self, name, content):
        """Upload *content* to the bucket and return the stored path."""
        content.seek(0)
        file_bytes = content.read()

        mime_type, _ = mimetypes.guess_type(name)
        mime_type = mime_type or "application/octet-stream"

        # upsert=True replaces existing objects with the same path
        self.client.storage.from_(self.bucket).upload(
            path=name,
            file=file_bytes,
            file_options={"content-type": mime_type, "upsert": "true"},
        )
        return name

    def delete(self, name):
        self.client.storage.from_(self.bucket).remove([name])

    def exists(self, name):
        try:
            # list with a prefix matching the exact file name
            parent = "/".join(name.split("/")[:-1])
            file_name = name.split("/")[-1]
            objects = self.client.storage.from_(self.bucket).list(parent)
            return any(obj["name"] == file_name for obj in (objects or []))
        except Exception:
            return False

    def url(self, name):
        """Return the public URL for the given file path."""
        return f"{self.public_url_base}/{name}"

    def size(self, name):
        parent = "/".join(name.split("/")[:-1])
        file_name = name.split("/")[-1]
        objects = self.client.storage.from_(self.bucket).list(parent)
        for obj in objects or []:
            if obj["name"] == file_name:
                return obj.get("metadata", {}).get("size", 0)
        return 0
