import threading
import socket
import time
import os
import hashlib
import Parse
from datetime import datetime
import Logs

# Cache directory and lock for thread safety
CACHE_DIR = "cache_files"
CACHE_LOCK = threading.Lock()

# Ensure the cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

def is_cache_valid(timestamp):
    # Example cache validity check (e.g., 60 seconds expiration)
    return (datetime.now() - timestamp).seconds < 60

def get_cache_key(host, request):
    """
    Generate a unique key for the cache based on host and request.
    """
    key_string = f"{host}:{request}"
    return hashlib.md5(key_string.encode('utf-8')).hexdigest()

def read_cache(cache_key):
    """
    Read cached response and timestamp from a file if it exists.
    """
    cache_file = os.path.join(CACHE_DIR, cache_key)
    try:
        with open(cache_file, 'rb') as f:
            timestamp = datetime.fromisoformat(f.readline().decode('utf-8').strip())
            response = f.read()
        return {'timestamp': timestamp, 'response': response}
    except (FileNotFoundError, ValueError):
        return None

def write_cache(cache_key, response):
    """
    Write the response and timestamp to a cache file.
    """
    cache_file = os.path.join(CACHE_DIR, cache_key)
    with open(cache_file, 'wb') as f:
        f.write(f"{datetime.now().isoformat()}\n".encode('utf-8'))
        f.write(response)

def cache_hit(clientSocket, host, port, modified_request, request_id):
    cache_key = get_cache_key(host, modified_request.decode("utf-8"))
    hit = False
    start_time = time.time()
    end_time = time.time()
    response = b''

    # Attempt to read from cache
    with CACHE_LOCK:  # Ensure thread-safe cache access
        cached_data = read_cache(cache_key)
        if cached_data and is_cache_valid(cached_data['timestamp']):
            print("Cache hit - Returning cached response.")
            clientSocket.sendall(cached_data['response'])
            hit = True
            response = cached_data['response']  # Assign cached response for logging
        else:
            print("Cache miss - Fetching from target server.")

    # If it's a cache miss, fetch from the target server
    if not hit:
        try:
            destinationSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            destinationSocket.connect((host, port))
            destinationSocket.sendall(modified_request)

            start_time = time.time()
            while True:
                data = destinationSocket.recv(1024)
                if not data:
                    break
                response += data
                if(len(data)<=0): break
                print(data.decode('utf-8'))
                clientSocket.sendall(data)
            end_time = time.time()
            print("please ya rab")
        except Exception as e:
            print(f"Error fetching response from target server: {e}")
            clientSocket.close()
            return
        finally:
            destinationSocket.close()

        # Store the response in cache
        with CACHE_LOCK:
            write_cache(cache_key, response)
    
    print("starting caching")
    # Determine cache status
    cache_status = "HIT" if hit else "MISS"

    response_status, content_type=Parse.extract_response_info(response)

    # Log the response
    try:
        Logs.log_response(
            request_id=request_id,
            cache_status=cache_status,
            response_status=response_status,
            content_type=content_type,
            response_size=len(response),
            response_time_ms=(end_time - start_time) * 1000 if not hit else 0
        )
    except Exception as e:
        print(f"Error logging response: {e}")
