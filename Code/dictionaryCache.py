import threading
import socket
import time
import Logs
from datetime import datetime

# Global cache and lock for thread safety
cache = {}
cache_lock = threading.Lock()  # Lock to synchronize cache access

def is_cache_valid(timestamp):
    # Example cache validity check (e.g., 60 seconds expiration)
    return (datetime.now() - timestamp).seconds < 60

def cache_hit(clientSocket, host, port, modified_request, request_id):
    cache_key = (host, modified_request.decode("utf-8"))
    hit = False
    start_time = time.time()
    end_time = time.time()
    response = b''

    with cache_lock:  # Ensure thread-safe cache access
        if cache_key in cache and is_cache_valid(cache[cache_key]['timestamp']):
            print("Cache hit - Returning cached response.")
            cached_response = cache[cache_key]['response']
            clientSocket.sendall(cached_response)
            hit = True
            response = cached_response  # Assign cached response for logging
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
                clientSocket.sendall(data)
            end_time = time.time()
        except Exception as e:
            print(f"Error fetching response from target server: {e}")
            clientSocket.close()
            return
        finally:
            destinationSocket.close()

        # Store the response in cache
        with cache_lock:
            cache[cache_key] = {
                'response': response,
                'timestamp': datetime.now()
            }

    # Determine cache status
    cache_status = "HIT" if hit else "MISS"

    # Parse the response headers (assuming HTTP)
    try:
        header_part = response.split(b'\r\n\r\n')[0].decode('utf-8')
        status_line = header_part.splitlines()[0]  # e.g., "HTTP/1.1 200 OK"
        response_status = int(status_line.split(' ')[1])
        content_type = next(
            (line.split(': ')[1] for line in header_part.splitlines() if line.startswith("Content-Type:")),
            "unknown"
        )
    except Exception as e:
        print(f"Error parsing response headers: {e}")
        response_status = None
        content_type = "unknown"

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