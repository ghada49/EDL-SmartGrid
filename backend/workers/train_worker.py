# backend/workers/train_worker.py
import os
from rq import Worker, SimpleWorker
from backend.rq_connection import redis_conn, train_queue

if __name__ == "__main__":
    worker_cls = Worker if os.name != "nt" else SimpleWorker
    worker = worker_cls([train_queue], connection=redis_conn)
    worker.work()
