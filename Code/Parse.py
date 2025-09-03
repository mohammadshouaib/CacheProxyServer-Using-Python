import re

def extract_request_line(request):
    # Decode the request safely
    try:
        lines = request.decode('utf-8', errors='replace').split('\r\n')
    except Exception as e:
        print(f"Debug: Error decoding request: {e}")
        raise ValueError("Invalid HTTP request: Cannot decode.")

    # Validate and parse the request line
    if not lines or len(lines[0].split()) != 3:
        print(f"Debug: Malformed request line: {lines[0] if lines else 'Empty Request'}")
        raise ValueError("Invalid HTTP request: Malformed request line.")

    method, url, version = lines[0].split()
    return method, url, version


def extract_host_port_from_request(request):
    match = re.search(r'Host:\s*([^\r\n:]+):?(\d+)?', request.decode('utf-8'))
    if not match:
        raise ValueError("Invalid HTTP request: Malformed 'Host:' header.")
    host = match.group(1)
    port = int(match.group(2)) if match.group(2) else 80
    return host, port

def modify_headers_for_proxy(request, host):
    # Split the request into headers and body
    request_parts = request.decode('utf-8', errors='replace').split('\r\n\r\n', 1)
    headers = request_parts[0].split('\r\n')
    body = request_parts[1] if len(request_parts) > 1 else ""

    # Prepare a new headers list
    modified_headers = []
    host_updated = False

    for line in headers:
        if line.lower().startswith('host:'):
            # Update the Host header
            modified_headers.append(f"Host: {host}")
            host_updated = True
        elif line.lower().startswith('connection:') or line.lower().startswith('proxy-authorization:'):
            # Remove headers that shouldn't be forwarded
            continue
        else:
            # Keep other headers unchanged
            modified_headers.append(line)

    # Add the Host header if it was missing
    if not host_updated:
        modified_headers.append(f"Host: {host}")

    # Reconstruct the modified request
    modified_request = '\r\n'.join(modified_headers) + '\r\n\r\n' + body
    return modified_request.encode('utf-8')

def  extract_response_info(response):
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
    finally:
        return response_status, content_type