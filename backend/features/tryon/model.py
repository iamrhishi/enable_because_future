"""
Try-on job model
"""

from typing import Optional
from shared.database import db_manager
from shared.logger import logger


class TryOnJob:
    """Try-on job data model"""
    
    def __init__(self, job_id: str = None, user_id: str = None, 
                 status: str = 'queued', progress: int = 0,
                 result_url: str = None, error_message: str = None,
                 created_at: str = None, updated_at: str = None, **kwargs):
        self.job_id = job_id
        self.user_id = user_id
        self.status = status
        self.progress = progress
        self.result_url = result_url
        self.error_message = error_message
        self.created_at = created_at
        self.updated_at = updated_at
        self._data = kwargs
    
    @classmethod
    def get_by_id(cls, job_id: str, user_id: str = None) -> Optional['TryOnJob']:
        """Get try-on job by ID"""
        logger.info(f"TryOnJob.get_by_id: ENTRY - job_id={job_id}, user_id={user_id}")
        try:
            if user_id:
                result = db_manager.execute_query(
                    "SELECT * FROM tryon_jobs WHERE job_id = ? AND user_id = ?",
                    (job_id, user_id),
                    fetch_one=True
                )
            else:
                result = db_manager.execute_query(
                    "SELECT * FROM tryon_jobs WHERE job_id = ?",
                    (job_id,),
                    fetch_one=True
                )
            
            if result:
                job = cls(**dict(result))
                logger.info(f"TryOnJob.get_by_id: EXIT - Job found, status={job.status}")
                return job
            logger.info(f"TryOnJob.get_by_id: EXIT - Job not found")
            return None
        except Exception as e:
            logger.exception(f"TryOnJob.get_by_id: EXIT - Error: {str(e)}")
            raise
    
    @classmethod
    def get_by_user(cls, user_id: str, status: str = None, limit: int = 50) -> list:
        """Get try-on jobs for a user"""
        logger.info(f"TryOnJob.get_by_user: ENTRY - user_id={user_id}, status={status}")
        try:
            query = "SELECT * FROM tryon_jobs WHERE user_id = ?"
            params = [user_id]
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            results = db_manager.execute_query(query, tuple(params), fetch_all=True)
            jobs = [cls(**dict(row)) for row in results] if results else []
            logger.info(f"TryOnJob.get_by_user: EXIT - Found {len(jobs)} jobs")
            return jobs
        except Exception as e:
            logger.exception(f"TryOnJob.get_by_user: EXIT - Error: {str(e)}")
            raise
    
    def to_dict(self) -> dict:
        """Convert try-on job to dictionary"""
        # Filter out bytes objects and non-serializable values from _data
        import json
        filtered_data = {}
        if self._data:
            for k, v in self._data.items():
                # Skip bytes objects
                if isinstance(v, bytes):
                    continue
                # Test if value is JSON-serializable
                try:
                    json.dumps(v)
                    filtered_data[k] = v
                except (TypeError, ValueError):
                    # Convert datetime objects to strings
                    if hasattr(v, 'isoformat'):
                        filtered_data[k] = v.isoformat()
                    else:
                        continue
        
        return {
            'job_id': self.job_id,
            'user_id': self.user_id,
            'status': self.status,
            'progress': self.progress,
            'result_url': self.result_url,
            'error_message': self.error_message,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            **filtered_data
        }

