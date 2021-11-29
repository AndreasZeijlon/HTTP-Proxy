import socket
import json
import _thread
import sys

#PORT is set by the user
HOST = '127.0.0.1'
BUFFER_SIZE = 65536

BAD_URL = 'http://zebroid.ida.liu.se/error1.html'
BAD_CONTENT = 'http://zebroid.ida.liu.se/error2.html'
BAD_URL_HOST = 'zebroid.ida.liu.se'
BAD_WORDS = ["spongebob", "norrkoping", "britney spears", "paris hilton", "norrköping", "parishilton", "britneyspears"]


# Function to parse out the important fields of the request to a dict
def parse_request(request):
    try:
        parsed_request = {}
        if len(request) > 0:
            request_string = request.decode("utf-8")
            split_req_headers = request_string.split("\r\n")
            parsed_request["REQUEST"] = split_req_headers[0]
            split_req_headers = split_req_headers[1:-2]

            for line in range(len(split_req_headers)):
                temp_str = split_req_headers[line].split(": ")
                parsed_request[temp_str[0]] = temp_str[1]

            parsed_request["Connection"] = "close"
        return parsed_request
    except Exception:
        return {}

# Function to parse out the important fields of the response to a dict
def parse_response(http_response):
    try:
        response_dict = {}
        if len(http_response) > 0:
            response_string = http_response.decode("utf-8")
            response_headers = response_string.split("\r\n")
            response_dict["RESPONSE"] = response_headers[0]
            response_headers = response_headers[1:]

            for line in range(len(response_headers)):
                temp_list = response_headers[line].split(": ")
                if len(temp_list) > 1:
                    response_dict[temp_list[0]] = temp_list[1]
                elif len(temp_list[0]) > 0:
                    response_dict["Content"] = temp_list[0]
        return response_dict
    except Exception:
        # For error check if parse resposne is empty
        return 0
    
# This function creates a HTTP response which redirects to "bad content" or "bad url"
def redirect_url(url):
    return  "HTTP/1.1 302 Found\r\nLocation: " + url + "\r\nHost: " + BAD_URL_HOST + "\r\nConnection: close\r\n\r\n" 

# This function is used to convert a dict back to a bytes object - which is used in HTTP
def dict_to_bytes(http_dict, start_line):
    stringified_dict = http_dict[start_line] + "\r\n"
    for key in http_dict.keys():
        if not key == start_line:
            stringified_dict += key + ": " + http_dict[key] + "\r\n"
    stringified_dict += "\r\n"
    return str.encode(stringified_dict)
    
# This function searches through the content for bad words
def inappropiate_content(content):
    content = content.lower()
    if any(word in content for word in BAD_WORDS):
        return True
    else:
        return False

# Creates a connection between client and server
def create_connection(host, port):
    try:
        family, socktype, proto, canonname, sockaddr = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM, 0, 0)[0]
        socket_fd = socket.socket(family=family, type=socktype, proto=proto)
        socket_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        socket_fd.connect(sockaddr)
        return socket_fd
    except Exception as e:
        print("Connection error: ", e)

# Client part - Here the requests are handled
def client(request, browser_to_proxy):
    try:
        request_dict = parse_request(request)
        if request_dict:
            # Only interested in GET requests
            if "GET" in request_dict["REQUEST"]:
                if inappropiate_content(request_dict["REQUEST"]):
                    stringified_response = redirect_url(BAD_URL)
                    browser_to_proxy.send(str.encode(stringified_response))
                else:
                    proxy_to_web = create_connection(request_dict["Host"], 80)
                    request_bytes = dict_to_bytes(request_dict, "REQUEST")
                    proxy_to_web.sendall(request_bytes)

                    # As long as the webserver keeps sending data, keep passing it onto our server
                    while(True):
                        response = proxy_to_web.recv(BUFFER_SIZE)
                        response_dict = parse_response(response)
            
                        if response_dict:
                            if "Content-Type" in response_dict.keys():
                                if "text/html" in response_dict["Content-Type"]:
                                    if "Content" in response_dict.keys():
                                        if inappropiate_content(response_dict["Content"]):
                                            stringified_response = redirect_url(BAD_CONTENT)
                                            response = str.encode(stringified_response)
                            if "Content-Encoding" in response_dict.keys():
                                print("This response is encoded in: ", response_dict["Content-Encoding"])
                        if len(response) > 0:
                            browser_to_proxy.send(response)
                        else:
                            # No more data to send - end loop and close both connections
                            break
                    proxy_to_web.close()
        browser_to_proxy.close()
    except socket.error as se:
        print("socket error: ", se)
        # If error - close both connections
        if proxy_to_web:
            proxy_to_web.close()
        if browser_to_proxy:
            browser_to_proxy.close()
        sys.exit()

# This code lets the user provide a valid PORT number 
while(True):
    try:
        PORT = int(input("Enter your PORT number of choice\n"))
        if PORT < 1024 or PORT > 49151:
            print("Please choose a PORT number between 1024 and 49151")
        else:    
            print("Accepted. The port number is now: ", PORT)
            break
    except ValueError:
        print("The port number entered is not valid, try again")
    except PermissionError:
        print("This port number is not available, please choose one above 1024")
    except OverflowError:
        print("Port number is too big, try again")
    
# Creates a socket and binds it to chosen PORT
server_fd=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_fd.bind((HOST,PORT))
server_fd.listen(100)

# Server part - listens for requests sent from browser and creates new threads to handle them
while(True):
    try:
        new_connection, addr = server_fd.accept()
        valread = new_connection.recv(BUFFER_SIZE)
        _thread.start_new_thread(client, (valread, new_connection))
    except KeyboardInterrupt:
        if new_connection:
            new_connection.close()
        server_fd.close()
        sys.exit()
