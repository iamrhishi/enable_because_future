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
from typing import Dict, Optional, Tuple
from shared.database import db_manager
from shared.logger import logger
from shared.errors import ValidationError
from shared.analytics import track_event, EventType

# Queue limits per context.md line 89
MAX_QUEUE_SIZE = int(os.environ.get('MAX_QUEUE_SIZE', '50'))  # Max jobs in queue
# Raised from 120s after 2 real jobs (checksummed against production logs,
# user 02704f4a on 2026-08-17) failed outright at 173.1s and 316.5s -
# both legitimate runs of process_tryon's own retry/fallback system, which
# exists specifically to recover from Gemini's inconsistent output (the
# same inconsistency reported as a bug). That system's real-world worst
# case can exceed the old 120s ceiling on its own, converting a case that
# would have eventually succeeded into a guaranteed hard failure. 450s
# gives ~40% margin over the worst observed real duration.
JOB_TIMEOUT_SECONDS = int(os.environ.get('JOB_TIMEOUT_SECONDS', '450'))


class JobQueue:
    """In-memory job queue for async processing with quality guardrails"""
    
    def __init__(self):
        logger.info("JobQueue.__init__: ENTRY")
        self.queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
        self.jobs: Dict[str, Dict] = {}
        self.worker_thread = None
        self.running = False
        self.job_start_times: Dict[str, float] = {}  # Track job start times for timeout
        self._cleanup_stuck_jobs()  # Mark any stuck jobs from previous crash as failed
        self._start_worker()
        logger.info(f"JobQueue.__init__: EXIT - Initialized (max_queue_size={MAX_QUEUE_SIZE}, timeout={JOB_TIMEOUT_SECONDS}s)")

    def _cleanup_stuck_jobs(self):
        """
        Mark jobs stuck in 'processing' status as failed (from a previous crash).

        This runs on every JobQueue() instantiation - i.e. on every container
        instance's startup, not just after a real crash. Cloud Run routinely
        runs multiple instances concurrently, each with its own in-memory
        JobQueue; a 'processing' row can legitimately belong to a DIFFERENT,
        currently-alive instance that started it moments ago. Without the
        time filter below, instance B booting up would immediately mark
        instance A's brand-new, actively-running job as failed. Only jobs
        that have been 'processing' for longer than the max allowed job
        runtime (plus a safety margin) are actually abandoned.
        """
        try:
            import datetime
            cutoff = (
                datetime.datetime.utcnow() - datetime.timedelta(seconds=JOB_TIMEOUT_SECONDS + 30)
            ).strftime('%Y-%m-%d %H:%M:%S')
            stuck_jobs = db_manager.execute_query(
                "SELECT job_id FROM tryon_jobs WHERE status = 'processing' AND updated_at < ?",
                (cutoff,),
                fetch_all=True
            )
            if stuck_jobs:
                for job in stuck_jobs:
                    job_id = job['job_id']
                    db_manager.execute_query(
                        """UPDATE tryon_jobs
                           SET status = 'failed',
                               error_message = 'Server restarted while job was processing',
                               updated_at = CURRENT_TIMESTAMP
                           WHERE job_id = ?""",
                        (job_id,)
                    )
                    logger.warning(f"JobQueue._cleanup_stuck_jobs: Marked stuck job {job_id} as failed")
                logger.info(f"JobQueue._cleanup_stuck_jobs: Cleaned up {len(stuck_jobs)} stuck job(s)")
        except Exception as e:
            logger.warning(f"JobQueue._cleanup_stuck_jobs: Error: {e}")
    
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
                job_id = job_data.get('job_id', 'unknown')
                logger.info(f"JobQueue._worker_loop: Processing job {job_id}")
                try:
                    self._process_job(job_data)
                except Exception as process_error:
                    # Catch-all: ensure job is marked failed even if _process_job crashes
                    logger.exception(f"JobQueue._worker_loop: CRITICAL - Job {job_id} crashed: {process_error}")
                    try:
                        self._update_job_status(job_id, 'failed', error_message=f"Internal error: {str(process_error)[:200]}")
                        # Get user email for analytics
                        user_email_crash = None
                        try:
                            from shared.models.user import User
                            user_crash = User.get_by_id(job_data.get('user_id')) if job_data.get('user_id') else None
                            user_email_crash = user_crash.email if user_crash else None
                        except Exception:
                            pass
                        track_event(
                            EventType.TRYON_FAILED,
                            user_id=job_data.get('user_id'),
                            user_email=user_email_crash,
                            metadata={'job_id': job_id, 'error': str(process_error)[:500], 'reason': 'worker_crash'}
                        )
                    except Exception as update_error:
                        logger.error(f"JobQueue._worker_loop: Failed to update crashed job status: {update_error}")
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.exception(f"JobQueue._worker_loop: Error in worker loop: {str(e)}")
        logger.info("JobQueue._worker_loop: EXIT - Worker loop stopped")
    
    def _process_job(self, job_data: Dict):
        """Process a single job with timeout handling"""
        job_id = job_data['job_id']
        user_id = job_data.get('user_id')
        logger.info(f"JobQueue._process_job: ENTRY - job_id={job_id}")

        # Get user email for analytics
        user_email = None
        try:
            from shared.models.user import User
            user = User.get_by_id(user_id) if user_id else None
            user_email = user.email if user else None
        except Exception:
            pass

        # Track start time for timeout
        start_time = time.time()
        self.job_start_times[job_id] = start_time

        try:
            # Update job status to processing
            self._update_job_status(job_id, 'processing', progress=10)

            # Import here to avoid circular imports
            from features.tryon.service import process_tryon_with_fallback, _remove_background_local

            # Remove garment background here (in the worker, not the request handler) -
            # rembg can take anywhere from 1-50+s and the client is waiting on job
            # creation, not on this. Preprocessing/validation already ran synchronously
            # in the request handler (cheap, so it's fine to fail fast there).
            garment_image = job_data['garment_image']
            if job_data.get('skip_bg_removal'):
                logger.info(f"JobQueue._process_job: Skipping rembg - garment image already background-removed (cached)")
            elif isinstance(garment_image, list):
                garment_image = [_remove_background_local(img) for img in garment_image]
            else:
                garment_image = _remove_background_local(garment_image)

                # Cache the result against the wardrobe item, if applicable, so
                # future try-ons with this same item skip rembg entirely. Best
                # effort - a caching failure shouldn't fail the try-on job.
                wardrobe_item_for_bg_cache = job_data.get('wardrobe_item_for_bg_cache')
                if wardrobe_item_for_bg_cache:
                    try:
                        item_id, cache_user_id = wardrobe_item_for_bg_cache
                        from shared.storage import get_storage_service
                        from features.wardrobe.model import WardrobeItem
                        storage_service = get_storage_service()
                        stored_path = storage_service.upload_image(
                            garment_image, f"wardrobe/{cache_user_id}/{item_id}_nobg.png", content_type='image/png'
                        )
                        WardrobeItem.update_image_path_no_bg(item_id, cache_user_id, stored_path)
                        logger.info(f"JobQueue._process_job: Cached background-removed image for wardrobe item {item_id}")
                    except Exception as cache_error:
                        logger.warning(f"JobQueue._process_job: Failed to cache background-removed image: {str(cache_error)}")

            # Process try-on with timeout check
            logger.info(f"JobQueue._process_job: Calling process_tryon for job {job_id}")

            # Check timeout before processing
            elapsed = time.time() - start_time
            if elapsed > JOB_TIMEOUT_SECONDS:
                raise ValidationError(f"Job timeout: {elapsed:.1f}s > {JOB_TIMEOUT_SECONDS}s")

            result_data = process_tryon_with_fallback(
                job_data['person_image'],
                garment_image,
                job_data.get('garment_type', 'upper'),
                job_data.get('garment_details', None),  # Pass garment details for Gemini
                job_data.get('options', {})
            )
            
            # Check timeout after processing
            elapsed = time.time() - start_time
            if elapsed > JOB_TIMEOUT_SECONDS:
                raise ValidationError(f"Job exceeded timeout: {elapsed:.1f}s > {JOB_TIMEOUT_SECONDS}s")
            
            # Upload to local storage if result is base64 data URL
            result_url = result_data
            if result_data.startswith('data:image'):
                try:
                    from shared.storage import get_storage_service
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

            # Track try-on completion
            track_event(
                EventType.TRYON_COMPLETE,
                user_id=user_id,
                user_email=user_email,
                metadata={'job_id': job_id, 'elapsed_seconds': round(elapsed, 1)}
            )

            logger.info(f"JobQueue._process_job: EXIT - Job {job_id} completed successfully in {elapsed:.1f}s")

        except ValidationError as e:
            logger.exception(f"JobQueue._process_job: EXIT - Job {job_id} validation failed: {str(e)}")
            self._update_job_status(job_id, 'failed', error_message=f"Validation error: {str(e)}")
            track_event(
                EventType.TRYON_FAILED,
                user_id=user_id,
                user_email=user_email,
                metadata={'job_id': job_id, 'error': str(e), 'reason': 'validation'}
            )
        except Exception as e:
            elapsed = time.time() - start_time
            logger.exception(f"JobQueue._process_job: EXIT - Job {job_id} failed after {elapsed:.1f}s: {str(e)}")
            self._update_job_status(job_id, 'failed', error_message=str(e))
            track_event(
                EventType.TRYON_FAILED,
                user_id=user_id,
                user_email=user_email,
                metadata={'job_id': job_id, 'error': str(e), 'elapsed_seconds': round(elapsed, 1)}
            )
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
                   garment_type: str = 'upper', garment_details: Dict = None, options: Dict = None,
                   garment_url: str = None, skip_bg_removal: bool = False,
                   wardrobe_item_for_bg_cache: Optional[Tuple[int, str]] = None) -> str:
        """
        Create a new try-on job

        Per context.md: Enforce quality guardrails (max queue size)

        Args:
            garment_url: Source URL of the garment for reference
            skip_bg_removal: True if garment_image already has its background
                removed (e.g. loaded from a wardrobe item's cached version) -
                skips the rembg call in the worker.
            wardrobe_item_for_bg_cache: (item_id, user_id) to write the
                computed background-removed image back to, so future try-ons
                of this item can reuse it. None if not applicable/already cached.

        Returns:
            job_id: Unique job identifier

        Raises:
            ValidationError: If queue is full
        """
        logger.info(f"JobQueue.create_job: ENTRY - user_id={user_id}, garment_type={garment_type}, garment_url={garment_url[:50] if garment_url else None}")

        try:
            # Check queue size (quality guardrail)
            if self.queue.qsize() >= MAX_QUEUE_SIZE:
                logger.warning(f"JobQueue.create_job: Queue full ({self.queue.qsize()}/{MAX_QUEUE_SIZE})")
                raise ValidationError(f"Queue is full. Maximum {MAX_QUEUE_SIZE} jobs allowed. Please try again later.")

            job_id = str(uuid.uuid4())

            # Create job record in database (include garment_url)
            db_manager.get_lastrowid(
                """INSERT INTO tryon_jobs (job_id, user_id, status, progress, garment_url)
                   VALUES (?, ?, 'queued', 0, ?)""",
                (job_id, user_id, garment_url)
            )
            
            # Add to queue
            job_data = {
                'job_id': job_id,
                'user_id': user_id,
                'person_image': person_image,
                'garment_image': garment_image,
                'garment_type': garment_type,
                'garment_details': garment_details,  # For Gemini API
                'options': options or {},
                'skip_bg_removal': skip_bg_removal,
                'wardrobe_item_for_bg_cache': wardrobe_item_for_bg_cache,
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


# Global job queue instance - lazy initialization to avoid blocking on import
_job_queue_instance = None
_lock = threading.Lock()

def get_job_queue():
    """Get or create job queue instance (lazy initialization)"""
    global _job_queue_instance
    if _job_queue_instance is None:
        with _lock:
            # Double-check pattern
            if _job_queue_instance is None:
                _job_queue_instance = JobQueue()
    return _job_queue_instance
