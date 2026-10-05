"""Run independently: python -m performance_worker. One process per configured worker."""
from production_runtime import configure
configure()
import time,logging
from durable_jobs import run_one
from performance_store import prune
if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    last=0
    while True:
        try:
            if time.time()-last>3600:prune();last=time.time()
            if not run_one():time.sleep(1)
        except Exception:
            logging.exception('Worker storage failure');time.sleep(5)
