import json
import requests
import time

from dataclasses import dataclass
from multiprocessing import Process, Queue
from multiprocessing.queues import Empty as Queue_Empty
from os.path import basename
from pprint import pprint
from typing import Dict, List, Tuple, Union
from tasks.makespan.util import write_line_to_csv, TIQ_FILE_PREFIX
from tasks.util.faasm import (
    get_knative_headers,
    get_faasm_exec_time_from_json,
    get_faasm_worker_pods,
    get_faasm_invoke_host_port,
    flush_hosts as flush_faasm_hosts,
)
from tasks.util.openmpi import (
    NATIVE_HOSTFILE,
    get_native_mpi_pods,
    run_kubectl_cmd,
)
from tasks.lammps.env import (
    DOCKER_LAMMPS_BINARY,
    DOCKER_LAMMPS_DIR,
    LAMMPS_FAASM_USER,
    LAMMPS_FAASM_FUNC,
    get_faasm_benchmark,
)

WORKLOAD_ALLOWLIST = ["wasm", "native", "batch"]
NATIVE_WORKLOADS = ["native", "batch"]
NOT_ENOUGH_SLOTS = "NOT_ENOUGH_SLOTS"
QUEUE_TIMEOUT_SEC = 10
QUEUE_SHUTDOWN = "QUEUE_SHUTDOWN"


@dataclass
class TaskObject:
    task_id: int
    app: str
    world_size: int


@dataclass
class ResultQueueItem:
    task_id: int
    exec_time: float


@dataclass
class ExecutedTaskInfo:
    task_id: int
    # Times are in seconds and rounded to zero decimal places
    time_executing: float
    time_in_queue: float


@dataclass
class WorkQueueItem:
    master_pod: str
    task: TaskObject


def dequeue_with_timeout(
    queue: Queue, queue_str: str, silent: bool = False
) -> Union[ResultQueueItem, WorkQueueItem]:
    while True:
        try:
            result = queue.get(timeout=QUEUE_TIMEOUT_SEC)
            break
        except Queue_Empty:
            if not silent:
                print(
                    "Timed-out dequeuing from {}. Trying again...".format(
                        queue_str
                    )
                )
            continue
    return result


def thread_pool_thread(
    work_queue: Queue, result_queue: Queue, thread_idx: int
) -> None:
    """
    Loop for the worker threads in the thread pool. Each thread performs a
    blocking request to execute a task
    """
    print("Pool thread {} starting".format(thread_idx))

    work_queue: WorkQueueItem
    while True:
        work_item = dequeue_with_timeout(work_queue, "work queue", silent=True)

        # Check for shutdown message
        if work_item.master_pod == QUEUE_SHUTDOWN:
            break

        data_file = get_faasm_benchmark(work_item.task.app)["data"][0]
        # TODO - maybe less hacky way to detect workload here
        if "openmpi" in work_item.master_pod:
            native_cmdline = "-in {}/{}.faasm.native".format(
                DOCKER_LAMMPS_DIR, data_file
            )
            world_size = work_item.task.world_size
            mpirun_cmd = [
                "mpirun",
                "-np {}".format(world_size),
                "-hostfile {}".format(NATIVE_HOSTFILE),
                DOCKER_LAMMPS_BINARY,
                native_cmdline,
            ]
            mpirun_cmd = " ".join(mpirun_cmd)

            exec_cmd = [
                "exec",
                work_item.master_pod,
                "--",
                "su mpirun -c '{}'".format(mpirun_cmd),
            ]

            start = time.time()
            exec_output = run_kubectl_cmd("lammps", " ".join(exec_cmd))
            print(exec_output)
            actual_time = int(time.time() - start)
        else:
            # WASM specific data
            host, port = get_faasm_invoke_host_port()
            url = "http://{}:{}".format(host, port)
            knative_headers = get_knative_headers()

            # Prepare Faasm request
            file_name = basename(data_file)
            cmdline = "-in faasm://lammps-data/{}".format(file_name)
            # TODO - add migration check period here
            msg = {
                "user": LAMMPS_FAASM_USER,
                "function": LAMMPS_FAASM_FUNC,
                "cmdline": cmdline,
                "mpi_world_size": work_item.task.world_size,
                "async": True,
            }
            print("Posting to {} msg:".format(url))
            pprint(msg)

            # Post asynch request
            response = requests.post(
                url, json=msg, headers=knative_headers, timeout=None
            )
            # Get the async message id
            if response.status_code != 200:
                print(
                    "Initial request failed: {}:\n{}".format(
                        response.status_code, response.text
                    )
                )
            print("Response: {}".format(response.text))
            msg_id = int(response.text.strip())

            # Start polling for the result
            print("Polling message {}".format(msg_id))
            while True:
                interval = 2
                time.sleep(interval)

                status_msg = {
                    "user": LAMMPS_FAASM_USER,
                    "function": LAMMPS_FAASM_FUNC,
                    "status": True,
                    "id": msg_id,
                }
                response = requests.post(
                    url,
                    json=status_msg,
                    headers=knative_headers,
                )

                if response.text.startswith("RUNNING"):
                    continue
                elif response.text.startswith("FAILED"):
                    raise RuntimeError("Call failed")
                elif not response.text:
                    raise RuntimeError("Empty status response")
                else:
                    print("Call finished succesfully")

                # Get the executed time from the response
                result_json = json.loads(response.text, strict=False)
                actual_time = int(get_faasm_exec_time_from_json(result_json))
                print("Actual time: {}".format(actual_time))

                # Finally exit the polling loop
                break

        result_queue.put(ResultQueueItem(work_item.task.task_id, actual_time))

    print("Pool thread {} shutting down".format(thread_idx))


class SchedulerState:
    num_vms: int
    num_cores_per_vm: int

    total_slots: int
    total_available_slots: int

    # Pod names and pod map
    native_pod_names: List[str]
    native_pod_map: Dict[str, int] = {}
    wasm_pod_names: List[str]
    wasm_pod_map: Dict[str, int] = {}

    in_flight_tasks: Dict[int, List[Tuple[str, int]]] = {}

    # Keep track of the workload being executed
    current_workload: str = ""

    def __init__(self, num_vms: int, num_cores_per_vm: int):
        self.num_vms = num_vms
        self.num_cores_per_vm = num_cores_per_vm
        self.total_slots = num_vms * num_cores_per_vm
        self.total_available_slots = self.total_slots

    def init_pod_list(self):
        # Initialise pod names and pod map depending on the experiment
        if self.current_workload in NATIVE_WORKLOADS:
            # TODO - eventually different namespace for this experiment
            self.native_pod_names, _ = get_native_mpi_pods("lammps")
            for pod in self.native_pod_names:
                self.native_pod_map[pod] = self.num_cores_per_vm
        else:
            self.wasm_pod_names = get_faasm_worker_pods()
            for pod in self.wasm_pod_names:
                self.wasm_pod_map[pod] = self.num_cores_per_vm

    def remove_in_flight_task(self, task_id: int) -> None:
        if task_id not in self.in_flight_tasks:
            raise RuntimeError("Task {} not in-flight!".format(task_id))
        print("Removing task {} from in-flight tasks".format(task_id))

        # Return the slots to each pod
        scheduling_decision: List[Tuple[str, int]] = self.in_flight_tasks[
            task_id
        ]
        for pod, slots in scheduling_decision:
            if self.current_workload in NATIVE_WORKLOADS:
                self.native_pod_map[pod] += slots
            else:
                self.wasm_pod_map[pod] += slots
            self.total_available_slots += slots


class BatchScheduler:
    work_queue: Queue = Queue()
    result_queue: Queue = Queue()
    thread_pool: List[Process]
    state: SchedulerState
    one_task_per_node: bool = False

    def __init__(self, num_vms: int, num_slots_per_vm: int):
        self.state = SchedulerState(num_vms, num_slots_per_vm)

        print("Initialised batch scheduler with the following parameters:")
        print("\t- Number of VMs: {}".format(self.state.num_vms))
        print("\t- Cores per VM: {}".format(self.state.num_cores_per_vm))
        print(
            "\t- Schedule one task per node: {}".format(self.one_task_per_node)
        )

        # We are pessimistic with the number of threads and allocate 2 times
        # the number of VMs, as the minimum world size we will ever use is half
        # of a VM
        self.num_threads_in_pool = 2 * self.state.num_vms
        self.thread_pool = [
            Process(
                target=thread_pool_thread,
                args=(
                    self.work_queue,
                    self.result_queue,
                    i,
                ),
            )
            for i in range(self.num_threads_in_pool)
        ]
        print(
            "Initialised thread pool with {} threads".format(
                len(self.thread_pool)
            )
        )
        # Start the thread pool
        for thread in self.thread_pool:
            thread.start()

    def shutdown(self):
        shutdown_msg = WorkQueueItem(QUEUE_SHUTDOWN, TaskObject(-1, "-1", -1))
        for _ in range(self.num_threads_in_pool):
            self.work_queue.put(shutdown_msg)

        for thread in self.thread_pool:
            thread.join()

    # --------- Actual scheduling and accounting -------

    def schedule_task_to_pod(
        self, task: TaskObject
    ) -> Union[str, List[Tuple[str, int]]]:
        if self.state.total_available_slots < task.world_size:
            print(
                "Not enough slots to schedule task "
                "{} (needed: {} - have: {})".format(
                    task.task_id,
                    task.world_size,
                    self.state.total_available_slots,
                )
            )
            return NOT_ENOUGH_SLOTS

        scheduling_decision: List[Tuple[str, int]] = []
        left_to_assign: int = task.world_size
        if self.state.current_workload in NATIVE_WORKLOADS:
            pod_map = self.state.native_pod_map
        else:
            pod_map = self.state.wasm_pod_map
        for pod, num_slots in sorted(
            pod_map.items(), key=lambda item: item[1], reverse=True
        ):
            # Work out how many slots can we take up in this pod
            if self.one_task_per_node:
                # If we only allow one task per node, regardless of how many
                # slots we have left to assign, we take up all the node
                num_on_this_pod = self.state.num_cores_per_vm
            else:
                num_on_this_pod: int = min(num_slots, left_to_assign)
            scheduling_decision.append((pod, num_on_this_pod))

            # Update the global state, and the slots left to assign
            pod_map[pod] -= num_on_this_pod
            self.state.total_available_slots -= num_on_this_pod
            left_to_assign -= num_on_this_pod

            # If no more slots to assign, exit the loop
            if left_to_assign <= 0:
                break
        else:
            print(
                "Ran out of pods to assign task slots to, "
                "but still {} to assign".format(left_to_assign)
            )
            raise RuntimeError(
                "Scheduling error: inconsistent scheduler state"
            )

        # Before returning, persist the scheduling decision to state
        self.state.in_flight_tasks[task.task_id] = scheduling_decision

        return scheduling_decision

    def execute_tasks(
        self, tasks: List[TaskObject]
    ) -> Dict[int, ExecutedTaskInfo]:
        """
        Execute a list of tasks, and return details on the task execution
        """
        time_per_task: Dict[int, ExecutedTaskInfo] = {}
        executed_task_count: int = 0

        # If running a WASM workload, flush the hosts first
        if self.state.current_workload == "wasm":
            flush_faasm_hosts()

        # If running the `batch` workload, set the scheduler to allocate at
        # most one task per host
        if self.state.current_workload == "batch":
            self.one_task_per_node = True

        for t in tasks:
            # First, try to schedule the task with the current available
            # resources
            scheduling_decision = self.schedule_task_to_pod(t)

            # If we don't have enough resources, wait for results until enough
            # resources
            time_in_queue_start = time.time()
            while scheduling_decision == NOT_ENOUGH_SLOTS:
                result: ResultQueueItem

                result = dequeue_with_timeout(
                    self.result_queue, "result queue"
                )

                # Update our local records according to result
                self.state.remove_in_flight_task(result.task_id)
                if result.task_id not in time_per_task:
                    raise RuntimeError("Unrecognised task {}", result.task_id)
                time_per_task[result.task_id].time_executing = result.exec_time
                executed_task_count += 1

                # Write line to file
                write_line_to_csv(
                    self.state.current_workload,
                    TIQ_FILE_PREFIX,
                    self.num_tasks,
                    time_per_task[result.task_id].task_id,
                    time_per_task[result.task_id].time_in_queue,
                    time_per_task[result.task_id].time_executing,
                )

                # Try to schedule again
                scheduling_decision = self.schedule_task_to_pod(t)

            # Once we have been able to schedule the task, record the time it
            # took
            time_in_queue = int(time.time() - time_in_queue_start)
            time_per_task[t.task_id] = ExecutedTaskInfo(
                t.task_id, 0, time_in_queue
            )

            # Log the scheduling decision
            master_pod = scheduling_decision[0][0]
            print(
                "Scheduling native task "
                "{} ({} slots) with master pod {}".format(
                    t.task_id, t.world_size, master_pod
                )
            )

            # Lastly, put the scheduled task in the work queue
            self.work_queue.put(WorkQueueItem(master_pod, t))

        # Once we are done scheduling tasks, drain the result queue
        while executed_task_count < len(tasks):
            result = dequeue_with_timeout(self.result_queue, "result queue")

            # Update our local records according to result
            self.state.remove_in_flight_task(result.task_id)
            if result.task_id not in time_per_task:
                raise RuntimeError("Unrecognised task {}", result.task_id)
            time_per_task[result.task_id].time_executing = result.exec_time
            executed_task_count += 1

            # Write line to file
            write_line_to_csv(
                self.state.current_workload,
                TIQ_FILE_PREFIX,
                self.num_tasks,
                time_per_task[result.task_id].task_id,
                time_per_task[result.task_id].time_in_queue,
                time_per_task[result.task_id].time_executing,
            )

        # If running the `batch` workload, revert the changes made to allocate
        # at most one task per host
        if self.state.current_workload == "batch":
            self.one_task_per_node = False

        return time_per_task

    def run(
        self, workload: str, tasks: List[TaskObject]
    ) -> Dict[int, ExecutedTaskInfo]:
        """
        Main entrypoint to run a number of tasks. The required parameters are:
            - workload: "native", "batch" or "wasm"
            - tasks: a list of TaskObject's
        The method returns a dictionary with timing information to be plotted
        """
        if workload in WORKLOAD_ALLOWLIST:
            print(
                "Batch scheduler received request to execute "
                "{} {} tasks".format(len(tasks), workload)
            )
            self.state.current_workload = workload
            # Initialise the scheduler state and pod list
            self.state.init_pod_list()
            self.num_tasks = len(tasks)
        else:
            print("Unrecognised workload type: {}".format(workload))
            print("Allowed workloads are: {}".format(WORKLOAD_ALLOWLIST))
            raise RuntimeError("Unrecognised workload type")

        # Current limitations:
        # - Only LAMMPS apps for native workloads (will need to implement an
        #   equivalent to our migration task)
        return self.execute_tasks(tasks)
