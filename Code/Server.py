import socket
import Logs
import Filter
import Cache
import threading
import Parse
from concurrent.futures import ThreadPoolExecutor

# Maximum number of worker threads in the thread pool
MAX_THREADS = 12

def handle_client_request(clientSocket):
    print("handling client request")
    try:
        # Extract client details
        client_ip, client_port = clientSocket.getpeername()

        # NEW 
        clientSocket.setblocking(False)

        # Read and parse the client request
        request = b''
        while True:
            try:
                data = clientSocket.recv(1024)
                if not data:
                    break
                request += data
                print(f"{data.decode('utf-8')}")
            except:
                break


        # Extract the HTTP method
        method, url, protocol= Parse.extract_request_line(request)
        print(f"Request Method: {method}")

        # Extract target server address and port
        host, port = Parse.extract_host_port_from_request(request)
        print(f"Request Target: {host}:{port}")

        # Modify headers for proxy (e.g., set the 'Host' header)
        modified_request = Parse.modify_headers_for_proxy(request, host)
        print(modified_request.decode('utf-8'))

        # Log request
        request_id = Logs.log_request(
                                        client_ip=client_ip,
                                        client_port=client_port,
                                        target_host=host,
                                        target_port=port,
                                        method=method,
                                        url=url,
                                        protocol=protocol
                                    )

        #Check if filtered
        if Filter.isAccepted(host, clientSocket):
            print('filter accepted')
            Cache.cache_hit(clientSocket, host, port, modified_request, request_id)
        else :
            Logs.log_response(
            request_id=request_id,
            cache_status='MISS',
            response_status=403,
            content_type="text/html",
            response_size=0,
            response_time_ms=0
        )


    except Exception as e:
        # Log the error
        print('exception occured')
        Logs.log_request(client_ip=client_ip, client_port=client_port, 
                         target_host=("unknown"), 
                         target_port=(0), 
                         method=("unknown"), 
                         url=("unknown"), 
                         protocol=("unknown"), 
                         error_message=str(e)
                         )
    finally:
        clientSocket.close()
        print('thread socket closed')



def start_proxy_server():

    port = 8099

    # bind the proxy server to a specific address and port
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', port))

    # accept up to 32 simultaneous connections
    server.listen(64)

    print(f"Proxy server listening on port {port}...")

    # listen for incoming requests (for simplicity and low traffic)
    while True:
        clientSocket, addr = server.accept()
        print(f"Accepted connection from {addr[0]}:{addr[1]}")

        # create a thread to handle the client request
        clientHandler = threading.Thread(target=handle_client_request, args=(clientSocket,))
        clientHandler.start()
    
    #  Create a thread pool executor (for high traffic)
    # with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
    #     while True:
    #         client_socket, addr = server.accept()
    #         print(f"Accepted connection from {addr[0]}:{addr[1]}")

    #         # Submit the task to the thread pool
    #         executor.submit(handle_client_request, client_socket)


if __name__ == "__main__":
    Logs.init_db()
    start_proxy_server()
    


# python proxy_server.py