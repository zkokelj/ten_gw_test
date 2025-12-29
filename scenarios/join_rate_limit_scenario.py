import logging
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from gateway import Environment

logging.basicConfig(
    format='%(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    level=logging.INFO
)

# Configuration
NUM_REQUESTS = 5000  # Total number of requests to send
MAX_WORKERS = 100  # Number of parallel workers

def make_join_request(base_url: str):
    """Make a /join request and return status code."""
    try:
        response = requests.get(
            f"{base_url}/join/",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=10
        )
        return response.status_code
    except Exception as e:
        logging.error(f"Request failed: {e}")
        return 0

def main():
    env = Environment.UAT
    
    logging.info(f'Join rate limit test: {env.url}')
    logging.info(f'Sending {NUM_REQUESTS} requests with {MAX_WORKERS} workers...')
    logging.info('=' * 60)
    
    # Send parallel requests
    start_time = time.time()
    status_codes = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(make_join_request, env.url) for _ in range(NUM_REQUESTS)]
        
        for future in as_completed(futures):
            status_code = future.result()
            status_codes.append(status_code)
    
    elapsed = time.time() - start_time
    
    # Count results
    success = sum(1 for sc in status_codes if sc == 200)
    rate_limited = sum(1 for sc in status_codes if sc == 429)
    other = len(status_codes) - success - rate_limited
    
    # Report
    logging.info('=' * 60)
    logging.info(f'Completed in {elapsed:.2f} seconds')
    logging.info(f'  Success (200): {success}')
    logging.info(f'  Rate limited (429): {rate_limited}')
    if other > 0:
        logging.info(f'  Other: {other}')

if __name__ == "__main__":
    main()
