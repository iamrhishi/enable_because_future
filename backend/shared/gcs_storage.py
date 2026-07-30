"""
GCS-backed storage service - same interface as shared.storage.StorageService,
used instead of local disk when Config.GCS_BUCKET_NAME is set (required on
Cloud Run, whose filesystem is ephemeral and not shared across instances).

Objects are private (bucket has public access prevention enabled); callers
get back a time-limited v4 signed URL rather than a public link, since these
are personal photos (avatars, wardrobe items, try-on results).
"""

from datetime import timedelta
from typing import Optional
from shared.logger import logger
from shared.errors import ExternalServiceError
from config import Config


class GCSStorageService:
    """Cloud Storage-backed image storage, mirroring StorageService's interface."""

    def __init__(self):
        from google.cloud import storage as gcs_storage

        logger.info("GCSStorageService.__init__: ENTRY")
        self.bucket_name = Config.GCS_BUCKET_NAME
        self.client = gcs_storage.Client()
        self.bucket = self.client.bucket(self.bucket_name)
        self._signing_credentials = None
        logger.info(f"GCSStorageService.__init__: EXIT - bucket={self.bucket_name}")

    def _get_signing_credentials(self):
        """
        Cloud Run's ambient credentials (google.auth.compute_engine.Credentials)
        carry only a short-lived token, not a private key, so
        Blob.generate_signed_url() can't sign locally. Wrapping them in
        impersonated_credentials targeting the same service account routes
        signing through the IAM signBlob API instead - this is why
        roles/iam.serviceAccountTokenCreator was granted to the service
        account on itself.
        """
        if self._signing_credentials is None:
            import google.auth
            from google.auth import impersonated_credentials

            ambient_credentials, _ = google.auth.default()
            target_principal = getattr(ambient_credentials, 'service_account_email', None)
            if not target_principal or target_principal == 'default':
                target_principal = Config.GCS_SIGNING_SERVICE_ACCOUNT

            self._signing_credentials = impersonated_credentials.Credentials(
                source_credentials=ambient_credentials,
                target_principal=target_principal,
                target_scopes=['https://www.googleapis.com/auth/cloud-platform'],
                lifetime=3600,
            )
        return self._signing_credentials

    def upload_image(self, image_data: bytes, file_path: str,
                      content_type: str = 'image/png',
                      expiration_hours: int = None) -> str:
        """
        Upload image to GCS and return a STABLE relative path (e.g.
        '/images/wardrobe/user123/item456.png'), matching StorageService's
        contract exactly - NOT a signed URL. Callers persist this return
        value in the DB (image_path/avatar_path columns) for reuse across
        requests, so it must not expire. A fresh signed URL is generated
        on demand at serve time instead (see get_signed_url / app.py's
        /images/<path:filename> route).

        Args:
            image_data: Image bytes
            file_path: Object path within the bucket (e.g. 'wardrobe/user123/item456.png')
            content_type: MIME type
            expiration_hours: Unused for GCS (kept for interface parity with StorageService)

        Returns:
            Stable relative path string

        Raises:
            ExternalServiceError: If upload fails
        """
        file_path = file_path.lstrip('/')
        logger.info(f"GCSStorageService.upload_image: ENTRY - file_path={file_path}, size={len(image_data)} bytes")

        try:
            blob = self.bucket.blob(file_path)
            blob.upload_from_string(image_data, content_type=content_type)

            url = f"{Config.IMAGES_BASE_URL}/{file_path}"
            logger.info(f"GCSStorageService.upload_image: EXIT - uploaded gs://{self.bucket_name}/{file_path}")
            return url
        except Exception as e:
            logger.exception(f"GCSStorageService.upload_image: EXIT - Error: {str(e)}")
            raise ExternalServiceError(f"Failed to upload image: {str(e)}", service='storage')

    def get_signed_url(self, file_path: str, expiration_hours: int = None) -> str:
        """
        Generate a fresh time-limited signed URL for an existing object.
        Call this at serve time (never persist the result) - see
        app.py's /images/<path:filename> route.
        """
        file_path = file_path.lstrip('/')
        hours = expiration_hours if expiration_hours is not None else Config.GCS_SIGNED_URL_EXPIRATION_HOURS
        blob = self.bucket.blob(file_path)
        return blob.generate_signed_url(
            version='v4',
            expiration=timedelta(hours=hours),
            method='GET',
            credentials=self._get_signing_credentials(),
        )

    def delete_image(self, file_path: str) -> bool:
        """Delete an object from GCS. Returns True if deleted, False otherwise."""
        file_path = file_path.lstrip('/')
        logger.info(f"GCSStorageService.delete_image: ENTRY - file_path={file_path}")

        try:
            blob = self.bucket.blob(file_path)
            if not blob.exists():
                logger.warning(f"GCSStorageService.delete_image: Object not found: {file_path}")
                return False
            blob.delete()
            logger.info(f"GCSStorageService.delete_image: EXIT - Deleted: {file_path}")
            return True
        except Exception as e:
            logger.exception(f"GCSStorageService.delete_image: EXIT - Error: {str(e)}")
            return False

    def get_image(self, file_path: str) -> bytes:
        """
        Download object bytes from GCS.

        Raises:
            ExternalServiceError: If object not found or download fails
        """
        file_path = file_path.lstrip('/')
        logger.info(f"GCSStorageService.get_image: ENTRY - file_path={file_path}")

        try:
            blob = self.bucket.blob(file_path)
            if not blob.exists():
                raise ExternalServiceError(f"Image not found: {file_path}", service='storage')
            data = blob.download_as_bytes()
            logger.info(f"GCSStorageService.get_image: EXIT - Loaded {len(data)} bytes")
            return data
        except ExternalServiceError:
            raise
        except Exception as e:
            logger.exception(f"GCSStorageService.get_image: EXIT - Error: {str(e)}")
            raise ExternalServiceError(f"Failed to read image: {str(e)}", service='storage')

    def delete_prefix(self, prefix: str) -> int:
        """
        Delete every object under a path prefix (e.g. 'wardrobe/user123/').
        Used for GDPR erasure - removes all of a user's files across
        avatars/wardrobe/tryon-results in one call, regardless of how many
        individual items exist.

        Returns:
            Number of objects deleted
        """
        prefix = prefix.lstrip('/')
        count = 0
        for blob in self.client.list_blobs(self.bucket_name, prefix=prefix):
            blob.delete()
            count += 1
        logger.info(f"GCSStorageService.delete_prefix: Deleted {count} objects under {prefix}")
        return count

    def save_garment_image(self, image_data: bytes, user_id: str, garment_id: str) -> str:
        """Save a garment image using the standard wardrobe storage convention."""
        file_path = f"wardrobe/{user_id}/{garment_id}.png"
        return self.upload_image(image_data, file_path, content_type='image/png')

    def get_image_path(self, file_path: str) -> Optional[str]:
        """No local filesystem path exists for GCS-backed objects."""
        return None
