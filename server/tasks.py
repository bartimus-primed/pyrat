import queue
import json

class Task:
    """ A task is assigned for each command that is queued by the operator, allows for simple state tracking """
    def __init__(self, command):
        self.command = command
        self.result = ""
        self.requested = False
        self.status = "Awaiting Client to Request Task"
    
    def task_result(self, result):
        """ 
        If a result is received the task is marked complete, this doesn't mean the command executed correctly.
        It simply means the client returned a result, which could be an error...
        """
        self.result = result
        self.status = "Task Completed"

    def task_requested(self):
        """
        A client connected and grabbed a task, updating the status of the task.
        """
        self.requested = True
        self.status = "Awaiting Client to Send Result"

    def get_status(self):
        return self.status

    def __repr__(self):
        return self.command

    def toJson(self):
        """ 
        Provides the ability to send the task to the client in json.
        Needs to be further checked to ensure errors are handled correctly. 
        """
        return json.dumps(self, default=lambda this: this.__dict__).encode("utf-8")
    def toPrettyPrint(self):
        return json.dumps(self, default=lambda this: this.__dict__, indent=4)


class Task_Manager:
    """
    The main workhorse of the application. Keeps track of the tasks and interfaces between the Operator and Backend.
    Only cares about 3 things:
        - unstarted_tasks <- Tasks that have been queued
        - started_tasks <- Tasks that have been picked up
        - completed_tasks <- Tasks that have been assigned a result 
        NOTE: self.completed_tasks is a LIST not a Queue, incase you need to interface with it.
        NOTE: The result could be an error. Completed != Successful
    Uses python's STDLIB queue since it uses a LIFO queue by default.
    """
    def __init__(self):
        self.unstarted_tasks = queue.Queue()
        """ Tasks that have been queued """
        self.started_tasks = queue.Queue()
        """ Tasks that have been picked up """
        self.completed_tasks = []
        """ Tasks that have been assigned a result """

    def add_task(self, task):
        self.unstarted_tasks.put(task)

    def get_task(self):
        """ Gets a task from the unstarted queue, updates its status and puts it in the started queue """
        if self.unstarted_tasks._qsize() == 0:
            return json.dumps("No Queued Tasks").encode("utf-8")
        selected_task = self.unstarted_tasks.get()
        selected_task.task_requested()
        self.started_tasks.put(selected_task)
        return selected_task.toJson()
    
    def complete_task(self, result):
        """ 
        Gets a task from the started queue, updates its status and puts it in the completed list
        """
        if self.started_tasks._qsize() == 0:
            return("No Started Tasks")
        selected_task = self.started_tasks.get()
        selected_task.task_result(result)
        self.log_to_file(selected_task)
        self.completed_tasks.append(selected_task)

    def get_completed_tasks(self):
        try:
            print(self.completed_tasks[-1].toPrettyPrint())
        except:
            print(f"No completed commands in history")
        print(f"{self.unstarted_tasks._qsize()} task(s) queued")
        print(f"{self.started_tasks._qsize()} task(s) awaiting completion")
        print(f"{len(self.completed_tasks)} task(s) completed")

        return self.completed_tasks

    def log_to_file(self, entry_to_write):
        """
        Sadly we have to do 2 calls to the filesystem one for read and one for write
        it seems like python's json library doesn't like play nice with a + attribute (e.g. w+ a+ r+).
        I don't have enough time to troubleshoot it right now. If you hire me though, I can! :D

        I tried quite a few things to get it working with only one call, but even when it did read
        the json, it would then append to the file instead of overwriting all of it. This leads to 
        a corrupt json file since you have two seperate data structures in it.

        This might actually be a bug in the standard library, I'll probably look over the STDLIB code later.
        """
        current_data = {}
        with open("session_log.json", "r") as f:
            try:
                current_data = json.load(f)
            except:
                current_data["OUTPUT_LOG"] = []
        with open("session_log.json", "w") as f:
            current_data["OUTPUT_LOG"].append(entry_to_write.__dict__)
            json.dump(current_data, f, indent=4)
    
    def kill_client(self):
        self.unstarted_tasks = queue.Queue(1)
        self.started_tasks = queue.Queue(1)
        self.add_task(Task("KILL"))