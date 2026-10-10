"""Bounded, Qt-independent jobs. Cancellation is cooperative and explicit."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
import threading
import time
import uuid
from backend.dependencies import clean_output
from backend.paths import SafetyError


class JobCancelled(Exception): pass


@dataclass
class JobContext:
    cancelled: threading.Event = field(default_factory=threading.Event)
    progress: object = lambda *args: None
    cancellable: bool = True

    def checkpoint(self):
        if self.cancellable and self.cancelled.is_set(): raise JobCancelled('Cancelled before the next safe stage')

    def report(self, message, percent=None):
        self.progress(clean_output(message), percent)


@dataclass
class Job:
    name: str
    generation: int = 0
    context: JobContext = field(default_factory=JobContext)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    state: str = 'queued'
    result: object = None
    error: dict | None = None
    exception: Exception | None = None
    logs: list = field(default_factory=list)
    future: object = None

    def cancel(self):
        if not self.context.cancellable or self.state in {'succeeded', 'failed', 'cancelled'}: return False
        self.context.cancelled.set()
        return True


class JobManager:
    def __init__(self, concurrency=2, capacity=32):
        self.executor = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix='cdm-job')
        self.capacity = threading.BoundedSemaphore(capacity)
        self.lock = threading.Lock()
        self.jobs = []

    def submit(self, job, function):
        if not self.capacity.acquire(blocking=False): raise SafetyError('Background job queue is full; wait for a job to finish')
        with self.lock: self.jobs.append(job)
        progress = job.context.progress
        def report(message, percent=None):
            job.logs = (job.logs + [{'time': time.time(), 'message': clean_output(message), 'percent': percent}])[-300:]
            progress(message, percent)
        job.context.progress = report
        def run():
            try:
                job.context.checkpoint()
                job.state = 'running'; job.context.report(job.name)
                job.result = function(job.context)
                job.context.checkpoint()
                job.state = 'succeeded'
            except JobCancelled:
                job.state = 'cancelled'
            except Exception as error:
                job.state = 'failed'; job.exception = error
                job.error = {'category': type(error).__name__, 'message': clean_output(str(error)), 'job_id': job.id}
            finally:
                self.capacity.release()
                # Completed results can contain entire catalogues/source maps.
                # Their caller owns the result; the pool retains active jobs only.
                with self.lock: self.jobs = [active for active in self.jobs if active is not job]
            return job
        try: job.future = self.executor.submit(run)
        except Exception:
            self.capacity.release()
            with self.lock: self.jobs = [active for active in self.jobs if active is not job]
            raise
        return job

    def shutdown(self):
        for job in self.jobs: job.cancel()
        self.executor.shutdown(wait=False)
