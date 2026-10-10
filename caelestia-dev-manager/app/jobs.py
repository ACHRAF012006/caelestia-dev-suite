"""Qt bridge for the shared scheduler; UI delivery always uses queued signals."""
from concurrent.futures import TimeoutError
from PySide6.QtCore import QObject, Signal, Slot, QTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton
from backend.jobs import JobManager, Job, JobContext

SCHEDULER = JobManager(concurrency=2)


class ReadJob(QObject):
    finished = Signal()

    def __init__(self, parent=None, name='Inspection', cancellable=True):
        super().__init__(parent)
        self.job = Job(name, context=JobContext(cancellable=cancellable))
        self.cancelled = self.job.context.cancelled
        self.timer = QTimer(self); self.timer.setInterval(20); self.timer.timeout.connect(self.poll)

    def run(self): raise NotImplementedError

    def start(self):
        SCHEDULER.submit(self.job, lambda context: self.run())
        self.timer.start()

    @Slot()
    def poll(self):
        if self.job.future is not None and self.job.future.done():
            self.timer.stop(); self.finished.emit()

    def isRunning(self): return self.job.future is not None and not self.job.future.done()

    def wait(self, milliseconds):
        try:
            if self.job.future is not None: self.job.future.result(timeout=milliseconds / 1000)
            return True
        except TimeoutError: return False


class Operation(ReadJob):
    progress = Signal(str, object)

    def __init__(self, name, function, parent, cancellable):
        super().__init__(parent, name, cancellable)
        self.function = function
        self.job.context.progress = self.progress.emit

    def run(self): return self.function(self.job.context)


class JobDialog(QDialog):
    def __init__(self, parent, name, function, cancellable=False):
        super().__init__(parent)
        self.setWindowTitle(name); self.resize(460, 180)
        layout = QVBoxLayout(self)
        self.message = QLabel('Queued…'); self.message.setWordWrap(True); layout.addWidget(self.message)
        self.progress = QProgressBar(); self.progress.setRange(0, 0); layout.addWidget(self.progress)
        self.cancel = QPushButton('Cancel after the current safe stage' if cancellable else 'Applying reviewed operation…')
        self.cancel.setEnabled(cancellable); self.cancel.clicked.connect(self.request_cancel); layout.addWidget(self.cancel)
        self.worker = Operation(name, function, self, cancellable)
        self.worker.progress.connect(self.update_progress); self.worker.finished.connect(self.completed)
        QTimer.singleShot(0, self.worker.start)

    @Slot(str, object)
    def update_progress(self, message, percent):
        self.message.setText(message)
        if percent is not None: self.progress.setRange(0, 100); self.progress.setValue(percent)

    def request_cancel(self):
        if self.worker.job.cancel(): self.cancel.setEnabled(False); self.message.setText('Cancelling at the next safe stage…')

    def reject(self):
        # Never close/destroy an active mutation worker. Escape/close requests
        # cancellation only for safe jobs and leaves its event loop alive.
        if self.worker.job.state in {'queued', 'running'}: self.request_cancel(); return
        super().reject()

    def closeEvent(self, event):
        if self.worker.job.state in {'queued', 'running'}: self.request_cancel(); event.ignore()
        else: event.accept()

    @Slot()
    def completed(self): self.accept()


def run_operation(parent, name, function, cancellable=False):
    dialog = JobDialog(parent, name, function, cancellable)
    previous = getattr(parent, "active_operation", None)
    parent.active_operation = dialog
    try: dialog.exec()
    finally:
        parent.active_operation = previous
        dialog.deleteLater()
    job = dialog.worker.job
    if job.exception is not None: raise job.exception
    if job.state == 'cancelled':
        from backend.jobs import JobCancelled
        raise JobCancelled('Operation cancelled at a safe stage')
    return job.result
