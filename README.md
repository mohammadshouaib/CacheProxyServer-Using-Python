# CacheProxyServer-Using-Python
A Python-based caching proxy server that forwards HTTP requests between clients and target servers. Includes features like caching, request logging, blacklist/whitelist filtering, and concurrent connections. Bonus features include HTTPS support, SSL/TLS decryption for debugging, and an optional web-based admin interface.


# Caching Proxy Server

## 📖 Description
This project implements a caching proxy server in Python. The proxy server forwards requests from clients to target servers, relays back responses, and enhances performance through caching. It also provides features such as logging, request filtering (blacklist/whitelist), and concurrent client handling.

Additional bonus features include HTTPS support, SSL/TLS decryption (MITM), and a web-based admin interface for managing the proxy.

---

## 🚀 Features

### Basic Proxy Functionality
- Accepts client requests and forwards them to target servers.
- Relays responses back to clients.
- Supports HTTP (and optionally HTTPS).

### Socket Programming
- Manages connections using raw sockets.
- Listens for client requests on a configurable port.
- Establishes connections with target servers for data transfer.

### Request Parsing
- Extracts host, port, HTTP method, and URL.
- Modifies headers (e.g., `Host`) as required.

### Threading
- Handles multiple clients concurrently via multithreading.

### Logging
Logs details such as:
- Client IP/port
- Target server address/port
- HTTP method and URL
- Request/response timestamps
- Error messages

### Content Caching
- Stores responses for repeated requests.
- Supports cache invalidation based on headers (`Cache-Control`, `Expires`) or custom timeout.

### Blacklist/Whitelist
- Restricts access to specific domains/IPs.
- Custom response for blocked requests.

---

## 🔒 Bonus Features

### HTTPS Proxy
- Supports tunneling HTTPS securely (without decryption).
- Optional SSL/TLS decryption (MITM) using self-signed certificates. *(For educational/debugging purposes only!)*

### Admin Interface
Web-based interface to:
- View/manage logs
- Inspect cache entries
- Configure blacklist/whitelist
- Display proxy usage statistics

---

## 🛠️ Requirements
- Python 3.8+
- Standard libraries: `socket`, `threading`, `logging`, `datetime`
- (Optional) `ssl` for HTTPS MITM
- (Optional) `flask` or `fastapi` for the admin interface

---

## 📂 Project Structure
proxy-server/
│── proxy.py # Main proxy server implementation
│── cache/ # Cache storage (if file-based caching used)
│── logs/ # Log files
│── config.json # Configuration file (blacklist/whitelist, cache settings, etc.)
│── README.md # Project documentation


---

## ▶️ Usage

### Clone the repository
```bash
git clone https://github.com/your-username/proxy-server.git
cd proxy-server




