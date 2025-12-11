"""
Local file storage service for try-on results and avatars
Stores images in local /images directory with organized structure
"""

import os
import base64
from pathlib import Path
from typing import Optional
from shared.logger import logger
from shared.errors import ExternalServiceError
from config import Config


class StorageService:
    """Local file storage service"""
    
    def __init__(self):
        logger.info("StorageService.__init__: ENTRY")
        
        # Get images directory from config (reads from environment)
        self.images_dir = Path(Config.IMAGES_DIR)
        self.base_url = Config.IMAGES_BASE_URL
        
        # Create images directory structure if it doesn't exist
        self.images_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.images_dir / 'tryon-results').mkdir(parents=True, exist_ok=True)
        (self.images_dir / 'avatars').mkdir(parents=True, exist_ok=True)
        (self.images_dir / 'wardrobe').mkdir(parents=True, exist_ok=True)
        
        logger.info(f"StorageService.__init__: EXIT - Initialized with images_dir={self.images_dir}, base_url={self.base_url}")
    
    def upload_image(self, image_data: bytes, file_path: str, 
                    content_type: str = 'image/png', 
                    expiration_hours: int = 24) -> str:
        """
        Upload image to local storage and return URL
        
        Args:
            image_data: Image bytes
            file_path: Path in storage (e.g., 'tryon-results/user123/job456.png')
            content_type: MIME type (default: image/png)
            expiration_hours: Not used for local storage (kept for compatibility)
            
        Returns:
            URL string (relative path from base URL)
            
        Raises:
            ExternalServiceError: If upload fails
        """
        logger.info(f"StorageService.upload_image: ENTRY - file_path={file_path}, size={len(image_data)} bytes")
        
        try:
            # Ensure file_path doesn't start with / and is within images directory
            file_path = file_path.lstrip('/')
            
            # Create full path
            full_path = self.images_dir / file_path
            
            # Ensure parent directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write image to file
            with open(full_path, 'wb') as f:
                f.write(image_data)
            
            # Generate URL (relative to base_url)
            url = f"{self.base_url}/{file_path}"
            
            logger.info(f"StorageService.upload_image: EXIT - Image saved to {full_path}, URL: {url}")
            return url
            
        except Exception as e:
            logger.exception(f"StorageService.upload_image: EXIT - Error: {str(e)}")
            raise ExternalServiceError(f"Failed to upload image: {str(e)}", service='storage')
    
    def delete_image(self, file_path: str) -> bool:
        """
        Delete image from local storage
        
        Args:
            file_path: Path in storage
            
        Returns:
            True if deleted, False otherwise
        """
        logger.info(f"StorageService.delete_image: ENTRY - file_path={file_path}")
        
        try:
            # Ensure file_path doesn't start with /
            file_path = file_path.lstrip('/')
            
            # Create full path
            full_path = self.images_dir / file_path
            
            # Check if file exists
            if not full_path.exists():
                logger.warning(f"StorageService.delete_image: File not found: {full_path}")
                return False
            
            # Delete file
            full_path.unlink()
            logger.info(f"StorageService.delete_image: EXIT - Deleted: {full_path}")
            return True
            
        except Exception as e:
            logger.exception(f"StorageService.delete_image: EXIT - Error: {str(e)}")
            return False
    
    def get_image(self, file_path: str) -> bytes:
        """
        Get image data from storage
        
        Args:
            file_path: Path in storage (e.g., 'wardrobe/user123/item456.png')
            
        Returns:
            Image bytes
            
        Raises:
            ExternalServiceError: If image not found or read fails
        """
        logger.info(f"StorageService.get_image: ENTRY - file_path={file_path}")
        
        try:
            # Ensure file_path doesn't start with /
            file_path = file_path.lstrip('/')
            
            # Create full path
            full_path = self.images_dir / file_path
            
            # Check if file exists
            if not full_path.exists():
                raise ExternalServiceError(f"Image not found: {file_path}", service='storage')
            
            # Read image bytes
            with open(full_path, 'rb') as f:
                image_data = f.read()
            
            logger.info(f"StorageService.get_image: EXIT - Loaded {len(image_data)} bytes from {full_path}")
            return image_data
            
        except ExternalServiceError:
            raise
        except Exception as e:
            logger.exception(f"StorageService.get_image: EXIT - Error: {str(e)}")
            raise ExternalServiceError(f"Failed to read image: {str(e)}", service='storage')
    
    def get_image_path(self, file_path: str) -> Optional[Path]:
        """
        Get full file system path for an image
        
        Args:
            file_path: Path in storage
            
        Returns:
            Path object if exists, None otherwise
        """
        try:
            file_path = file_path.lstrip('/')
            full_path = self.images_dir / file_path
            if full_path.exists():
                return full_path
            return None
        except Exception as e:
            logger.exception(f"StorageService.get_image_path: Error: {str(e)}")
            return None


# Global storage service instance
_storage_service = None


def get_storage_service() -> StorageService:
    """Get or create storage service instance"""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
