from queue_runner_example import celery_app

if __name__ == "__main__":
    celery_app.worker_main(["worker", "--loglevel=INFO"])
