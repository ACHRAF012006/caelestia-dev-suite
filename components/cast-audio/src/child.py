"""Exec a tracked child with Linux parent-death cleanup, preserving its PID."""
import ctypes
import os
import signal
import sys


def guard(parent):
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0 or os.getppid() != parent:
        raise SystemExit(1)


if __name__ == "__main__":
    guard(int(sys.argv[1]))
    os.execv(sys.argv[2], sys.argv[2:])
