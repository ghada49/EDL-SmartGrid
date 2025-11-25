# backend/rq_connection.py
import os
import redis
from rq import Queue

# Always read from REDIS_URL, default to the docker service name "redis"
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

redis_conn = redis.from_url(REDIS_URL)

# Training queue
train_queue = Queue("training", connection=redis_conn)
