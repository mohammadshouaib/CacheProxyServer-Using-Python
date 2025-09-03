from socket import *
serverName = "127.0.0.1"
serverPort = 8081
clientSocket = socket(AF_INET, SOCK_STREAM)
clientSocket.connect((serverName, serverPort))

test_request = (
    "GET /path HTTP/1.1\r\n"
    "Host: example.com\r\n"
    "Connection: close\r\n"
    # "Proxy-Authorization: Basic dXNlcjpwYXNz\r\n"
    "\r\n"
)


# Encode the request to bytes using utf-8
clientSocket.sendall(test_request.encode('utf-8'))

response = b''
while True:
    data = clientSocket.recv(1024)
    if not data or len(data)<1:
        break
    response += data
    print(data.decode('utf-8'))  # Print each chunk decoded
print(response.decode('utf-8'))
clientSocket.close()
