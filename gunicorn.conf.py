import multiprocessing

bind = "0.0.0.0:5000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gthread"
threads = 2  # each worker gets N Python threads
preload_app = True
timeout = 30  # kill hung requests
graceful_timeout = 30
keepalive = 5
loglevel = "info"
accesslog = "-"
errorlog = "-"
wsgi_app = "app:app"
