"""Production resource defaults; import before numerical libraries."""
import os

def configure():
    # Explicit MarketScope setting is the supported override. Host CPU discovery
    # can exceed the CPU quota actually available to a hosted instance.
    threads=str(max(1,min(8,int(os.environ.get('MARKETSCOPE_NUMERIC_THREADS','1')))))
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
        os.environ[key]=threads
    return threads
