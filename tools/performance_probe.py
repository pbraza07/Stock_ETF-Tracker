"""Queue probe for an isolated test database, not a production load generator."""
import argparse,sys,time,statistics
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from functools import partial
from durable_jobs import submit,poll

def sample(number,progress):progress(1,1,'Probe');return number

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--jobs',type=int,default=10);a=p.parse_args()
    times=[];jobs=[]
    for i in range(a.jobs):
        start=time.perf_counter();jobs.append(submit(partial(sample,i)));times.append(time.perf_counter()-start)
    deadline=time.monotonic()+120
    while not all(poll(token)['future'].done() for token in jobs):
        if time.monotonic()>deadline:raise TimeoutError('Worker did not complete probe within 120 seconds')
        time.sleep(.2)
    assert [poll(token)['future'].result() for token in jobs]==list(range(a.jobs))
    print({'completed':len(jobs),'submit_median_seconds':statistics.median(times),'submit_max_seconds':max(times)})
