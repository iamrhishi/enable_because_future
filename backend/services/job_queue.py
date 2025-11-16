"""
Async job queue for try-on processing
In-memory queue for V1, can be upgraded to Redis/Celery later
Per context.md: Enforce quality guardrails (size, file type, max queue, timeout)
"""

import queue
import threading
import uuid
import time
import os
from typing import Dict, Optional
from services.database import db_manager
from utils.logger import logger
from utils.errors import ValidationError

# Queue limits per context.md line 89
MAX_QUEUE_SIZE = int(os.environ.get('MAX_QUEUE_SIZE', '50'))  # Max jobs in queue
JOB_TIMEOUT_SECONDS = int(os.environ.get('JOB_TIMEOUT_SECONDS', '120'))  # 120 seconds per context.md


class JobQueue:
    """In-memory job queue for async processing with quality guardrails"""
    
    def __init__(self):
        logger.info("JobQueue.__init__: ENTRY")
        self.queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
        self.jobs: Dict[str, Dict] = {}
        self.worker_thread = None
        self.running = False
        self.job_start_times: Dict[str, float] = {}  # Track job start times for timeout
        self._start_worker()
        logger.info(f"JobQueue.__init__: EXIT - Initialized (max_queue_size={MAX_QUEUE_SIZE}, timeout={JOB_TIMEOUT_SECONDS}s)")
    
    def _start_worker(self):
        """Start background worker thread"""
        logger.info("JobQueue._start_worker: ENTRY")
        try:
            if not self.running:
                self.running = True
                self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
                self.worker_thread.start()
                logger.info("JobQueue._start_worker: EXIT - Worker thread started")
            else:
                logger.info("JobQueue._start_worker: EXIT - Worker already running")
        except Exception as e:
            logger.exception(f"JobQueue._start_worker: EXIT - Error: {str(e)}")
            raise
    
    def _worker_loop(self):
        """Worker loop that processes jobs from queue"""
        logger.info("JobQueue._worker_loop: ENTRY - Starting worker loop")
        while self.running:
            try:
                job_data = self.queue.get(timeout=1)
                logger.info(f"JobQueue._worker_loop: Processing job {job_data.get('job_id')}")
                self._process_job(job_data)
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.exception(f"JobQueue._worker_loop: Error in worker loop: {str(e)}")
        logger.info("JobQueue._worker_loop: EXIT - Worker loop stopped")
    
    def _process_job(self, job_data: Dict):
        """Process a single job with timeout handling"""
        job_id = job_data['job_id']
        logger.info(f"JobQueue._process_job: ENTRY - job_id={job_id}")
        
        # Track start time for timeout
        start_time = time.time()
        self.job_start_times[job_id] = start_time
        
        try:
            # Update job status to processing
            self._update_job_status(job_id, 'processing', progress=10)
            
            # Import here to avoid circular imports
            from services.ai_integration import process_tryon
            
            # Process try-on with timeout check
            logger.info(f"JobQueue._process_job: Calling process_tryon for job {job_id}")
            
            # Check timeout before processing
            elapsed = time.time() - start_time
            if elapsed > JOB_TIMEOUT_SECONDS:
                raise ValidationError(f"Job timeout: {elapsed:.1f}s > {JOB_TIMEOUT_SECONDS}s")
            
            result_data = process_tryon(
                job_data['person_image'],
                job_data['garment_image'],
                job_data.get('garment_type', 'upper'),
                job_data.get('options', {})
            )
            
            # Check timeout after processing
            elapsed = time.time() - start_time
            if elapsed > JOB_TIMEOUT_SECONDS:
                raise ValidationError(f"Job exceeded timeout: {elapsed:.1f}s > {JOB_TIMEOUT_SECONDS}s")
            
            # Upload to cloud storage if result is base64 data URL
            result_url = result_data
            if result_data.startswith('data:image'):
                try:
                    from services.storage import get_storage_service
                    import base64
                    from io import BytesIO
                    
                    # Extract image from base64 data URL
                    header, encoded = result_data.split(',', 1)
                    image_data = base64.b64decode(encoded)
                    
                    # Generate storage path
                    user_id = job_data.get('user_id', 'unknown')
                    storage_path = f"tryon-results/{user_id}/{job_id}.png"
                    
                    # Upload to storage
                    storage_service = get_storage_service()
                    result_url = storage_service.upload_image(
                        image_data,
                        storage_path,
                        content_type='image/png',
                        expiration_hours=24
                    )
                    logger.info(f"JobQueue._process_job: Uploaded result to storage: {storage_path}")
                except Exception as storage_error:
                    logger.warning(f"JobQueue._process_job: Storage upload failed, using base64: {str(storage_error)}")
                    # Keep base64 URL if storage fails
                    result_url = result_data
            
            # Update job status to done
            elapsed = time.time() - start_time
            self._update_job_status(job_id, 'done', progress=100, result_url=result_url)
            logger.info(f"JobQueue._process_job: EXIT - Job {job_id} completed successfully in {elapsed:.1f}s")
            
        except ValidationError as e:
            logger.exception(f"JobQueue._process_job: EXIT - Job {job_id} validation failed: {str(e)}")
            self._update_job_status(job_id, 'failed', error_message=f"Validation error: {str(e)}")
        except Exception as e:
            elapsed = time.time() - start_time
            logger.exception(f"JobQueue._process_job: EXIT - Job {job_id} failed after {elapsed:.1f}s: {str(e)}")
            self._update_job_status(job_id, 'failed', error_message=str(e))
        finally:
            # Clean up start time tracking
            if job_id in self.job_start_times:
                del self.job_start_times[job_id]
    
    def _update_job_status(self, job_id: str, status: str, progress: int = None, 
                          result_url: str = None, error_message: str = None):
        """Update job status in database"""
        logger.debug(f"JobQueue._update_job_status: ENTRY - job_id={job_id}, status={status}")
        
        try:
            updates = ['status = ?', 'updated_at = CURRENT_TIMESTAMP']
            values = [status]
            
            if progress is not None:
                updates.append('progress = ?')
                values.append(progress)
            
            if result_url:
                updates.append('result_url = ?')
                values.append(result_url)
            
            if error_message:
                updates.append('error_message = ?')
                values.append(error_message)
            
            values.append(job_id)
            
            query = f"UPDATE tryon_jobs SET {', '.join(updates)} WHERE job_id = ?"
            db_manager.execute_query(query, tuple(values))
            logger.debug(f"JobQueue._update_job_status: EXIT - Status updated successfully")
            
        except Exception as e:
            logger.exception(f"JobQueue._update_job_status: EXIT - Error: {str(e)}")
            raise
    
    def create_job(self, user_id: str, person_image: bytes, garment_image: bytes, 
                   garment_type: str = 'upper', options: Dict = None) -> str:
        """
        Create a new try-on job
        
        Per context.md: Enforce quality guardrails (max queue size)
        
        Returns:
            job_id: Unique job identifier
            
        Raises:
            ValidationError: If queue is full
        """
        logger.info(f"JobQueue.create_job: ENTRY - user_id={user_id}, garment_type={garment_type}")
        
        try:
            # Check queue size (quality guardrail)
            if self.queue.qsize() >= MAX_QUEUE_SIZE:
                logger.warning(f"JobQueue.create_job: Queue full ({self.queue.qsize()}/{MAX_QUEUE_SIZE})")
                raise ValidationError(f"Queue is full. Maximum {MAX_QUEUE_SIZE} jobs allowed. Please try again later.")
            
            job_id = str(uuid.uuid4())
            
            # Create job record in database
            db_manager.get_lastrowid(
                """INSERT INTO tryon_jobs (job_id, user_id, status, progress)
                   VALUES (?, ?, 'queued', 0)""",
                (job_id, user_id)
            )
            
            # Add to queue
            job_data = {
                'job_id': job_id,
                'user_id': user_id,
                'person_image': person_image,
                'garment_image': garment_image,
                'garment_type': garment_type,
                'options': options or {}
            }
            
            # Non-blocking put with timeout
            try:
                self.queue.put(job_data, block=False)
            except queue.Full:
                # Clean up database record
                db_manager.execute_query("DELETE FROM tryon_jobs WHERE job_id = ?", (job_id,))
                raise ValidationError(f"Queue is full. Maximum {MAX_QUEUE_SIZE} jobs allowed. Please try again later.")
            
            logger.info(f"JobQueue.create_job: EXIT - Job {job_id} created and queued (queue size: {self.queue.qsize()}/{MAX_QUEUE_SIZE})")
            return job_id
            
        except ValidationError:
            raise
        except Exception as e:
            logger.exception(f"JobQueue.create_job: EXIT - Error: {str(e)}")
            raise
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get job status from database"""
        logger.info(f"JobQueue.get_job_status: ENTRY - job_id={job_id}")
        
        try:
            job = db_manager.execute_query(
                "SELECT * FROM tryon_jobs WHERE job_id = ?",
                (job_id,),
                fetch_one=True
            )
            logger.info(f"JobQueue.get_job_status: EXIT - Job found: {job is not None}")
            return job
        except Exception as e:
            logger.exception(f"JobQueue.get_job_status: EXIT - Error: {str(e)}")
            raise
    
    def stop(self):
        """Stop the worker thread"""
        logger.info("JobQueue.stop: ENTRY")
        try:
            self.running = False
            if self.worker_thread:
                self.worker_thread.join(timeout=5)
            logger.info("JobQueue.stop: EXIT - Worker stopped")
        except Exception as e:
            logger.exception(f"JobQueue.stop: EXIT - Error: {str(e)}")
            raise


# Global job queue instance
job_queue = JobQueue()
