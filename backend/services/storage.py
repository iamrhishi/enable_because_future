"""
Cloud storage service for try-on results and avatars
Supports S3 and GCS with signed URLs
Per context.md: Store results in S3/GCS, return short-lived signed URLs
"""

import os
import base64
from datetime import datetime, timedelta
from typing import Optional
from utils.logger import logger
from utils.errors import ExternalServiceError
from config import Config


class StorageService:
    """Cloud storage service abstraction"""
    
    def __init__(self):
        logger.info("StorageService.__init__: ENTRY")
        # Default to GCS per user request, but allow override
        self.provider = os.environ.get('STORAGE_PROVIDER', 'gcs').lower()
        logger.info(f"StorageService.__init__: Using provider={self.provider}")
        
        if self.provider == 'gcs':
            self._init_gcs()
        elif self.provider == 's3':
            self._init_s3()
        else:
            logger.warning(f"StorageService.__init__: Unknown provider={self.provider}, storage disabled")
            self.provider = None
        
        logger.info("StorageService.__init__: EXIT")
    
    def _init_s3(self):
        """Initialize AWS S3 client"""
        logger.info("StorageService._init_s3: ENTRY")
        try:
            import boto3  # type: ignore
            from botocore.exceptions import ClientError  # type: ignore
            
            self.boto3 = boto3
            self.ClientError = ClientError
            
            # Get credentials from config
            aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
            aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
            self.bucket_name = os.environ.get('AWS_S3_BUCKET')
            self.region = os.environ.get('AWS_REGION', 'us-east-1')
            
            if not aws_access_key or not aws_secret_key or not self.bucket_name:
                logger.warning("StorageService._init_s3: AWS credentials not configured, S3 disabled")
                self.provider = None
                return
            
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=self.region
            )
            logger.info(f"StorageService._init_s3: S3 client initialized for bucket={self.bucket_name}")
        except ImportError:
            logger.warning("StorageService._init_s3: boto3 not installed, S3 disabled")
            self.provider = None
        except Exception as e:
            logger.exception(f"StorageService._init_s3: Failed to initialize S3: {str(e)}")
            self.provider = None
        finally:
            logger.info("StorageService._init_s3: EXIT")
    
    def _init_gcs(self):
        """Initialize Google Cloud Storage client"""
        logger.info("StorageService._init_gcs: ENTRY")
        try:
            from google.cloud import storage  # type: ignore
            from google.api_core import exceptions as gcs_exceptions  # type: ignore
            
            self.storage = storage
            self.GoogleCloudError = gcs_exceptions.GoogleAPIError  # Base exception for GCS errors
            
            # Get credentials from config
            gcs_credentials_path = os.environ.get('GCS_CREDENTIALS_PATH')
            self.bucket_name = os.environ.get('GCS_BUCKET_NAME')
            
            if not self.bucket_name:
                logger.warning("StorageService._init_gcs: GCS bucket not configured, GCS disabled")
                self.provider = None
                return
            
            if gcs_credentials_path:
                self.storage_client = storage.Client.from_service_account_json(gcs_credentials_path)
            else:
                # Use default credentials
                self.storage_client = storage.Client()
            
            self.bucket = self.storage_client.bucket(self.bucket_name)
            logger.info(f"StorageService._init_gcs: GCS client initialized for bucket={self.bucket_name}")
        except ImportError:
            logger.warning("StorageService._init_gcs: google-cloud-storage not installed, GCS disabled")
            self.provider = None
        except Exception as e:
            logger.exception(f"StorageService._init_gcs: Failed to initialize GCS: {str(e)}")
            self.provider = None
        finally:
            logger.info("StorageService._init_gcs: EXIT")
    
    def upload_image(self, image_data: bytes, file_path: str, 
                    content_type: str = 'image/png', 
                    expiration_hours: int = 24) -> str:
        """
        Upload image to cloud storage and return signed URL
        
        Args:
            image_data: Image bytes
            file_path: Path in storage (e.g., 'tryon-results/user123/job456.png')
            content_type: MIME type (default: image/png)
            expiration_hours: Signed URL expiration in hours (default: 24)
            
        Returns:
            Signed URL string
            
        Raises:
            ExternalServiceError: If upload fails
        """
        logger.info(f"upload_image: ENTRY - file_path={file_path}, size={len(image_data)} bytes")
        
        if not self.provider:
            logger.warning("upload_image: Storage provider not configured, returning base64 data URL")
            # Fallback to base64 if storage not configured
            result_base64 = base64.b64encode(image_data).decode('utf-8')
            return f"data:{content_type};base64,{result_base64}"
        
        try:
            if self.provider == 's3':
                return self._upload_to_s3(image_data, file_path, content_type, expiration_hours)
            elif self.provider == 'gcs':
                return self._upload_to_gcs(image_data, file_path, content_type, expiration_hours)
            else:
                raise ExternalServiceError(f"Unknown storage provider: {self.provider}", service='storage')
        except ExternalServiceError:
            raise
        except Exception as e:
            logger.exception(f"upload_image: EXIT - Error: {str(e)}")
            raise ExternalServiceError(f"Failed to upload image: {str(e)}", service='storage')
    
    def _upload_to_s3(self, image_data: bytes, file_path: str, 
                     content_type: str, expiration_hours: int) -> str:
        """Upload to AWS S3 and generate signed URL"""
        logger.info(f"_upload_to_s3: ENTRY - file_path={file_path}")
        
        try:
            # Upload file
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=image_data,
                ContentType=content_type
            )
            logger.info(f"_upload_to_s3: File uploaded to s3://{self.bucket_name}/{file_path}")
            
            # Generate signed URL
            signed_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': file_path},
                ExpiresIn=expiration_hours * 3600  # Convert hours to seconds
            )
            
            logger.info(f"_upload_to_s3: EXIT - Signed URL generated (expires in {expiration_hours}h)")
            return signed_url
            
        except self.ClientError as e:
            logger.exception(f"_upload_to_s3: EXIT - S3 error: {str(e)}")
            raise ExternalServiceError(f"S3 upload failed: {str(e)}", service='s3')
        except Exception as e:
            logger.exception(f"_upload_to_s3: EXIT - Error: {str(e)}")
            raise ExternalServiceError(f"S3 upload failed: {str(e)}", service='s3')
    
    def _upload_to_gcs(self, image_data: bytes, file_path: str, 
                      content_type: str, expiration_hours: int) -> str:
        """Upload to Google Cloud Storage and generate signed URL"""
        logger.info(f"_upload_to_gcs: ENTRY - file_path={file_path}")
        
        try:
            # Upload file
            blob = self.bucket.blob(file_path)
            blob.upload_from_string(image_data, content_type=content_type)
            logger.info(f"_upload_to_gcs: File uploaded to gs://{self.bucket_name}/{file_path}")
            
            # Generate signed URL
            expiration = datetime.utcnow() + timedelta(hours=expiration_hours)
            signed_url = blob.generate_signed_url(
                expiration=expiration,
                method='GET'
            )
            
            logger.info(f"_upload_to_gcs: EXIT - Signed URL generated (expires in {expiration_hours}h)")
            return signed_url
            
        except Exception as e:
            logger.exception(f"_upload_to_gcs: EXIT - Error: {str(e)}")
            raise ExternalServiceError(f"GCS upload failed: {str(e)}", service='gcs')
    
    def delete_image(self, file_path: str) -> bool:
        """
        Delete image from cloud storage
        
        Args:
            file_path: Path in storage
            
        Returns:
            True if deleted, False otherwise
        """
        logger.info(f"delete_image: ENTRY - file_path={file_path}")
        
        if not self.provider:
            logger.warning("delete_image: Storage provider not configured")
            return False
        
        try:
            if self.provider == 's3':
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_path)
                logger.info(f"delete_image: EXIT - Deleted from S3: {file_path}")
                return True
            elif self.provider == 'gcs':
                blob = self.bucket.blob(file_path)
                blob.delete()
                logger.info(f"delete_image: EXIT - Deleted from GCS: {file_path}")
                return True
            else:
                return False
        except Exception as e:
            logger.exception(f"delete_image: EXIT - Error: {str(e)}")
            return False


# Global storage service instance
_storage_service = None


def get_storage_service() -> StorageService:
    """Get or create storage service instance"""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service

