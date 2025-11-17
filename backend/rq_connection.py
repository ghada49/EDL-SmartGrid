from redis import Redis
from rq import Queue

redis_conn = Redis(host="localhost", port=6379, db=0)
train_queue = Queue("train-queue", connection=redis_conn)
