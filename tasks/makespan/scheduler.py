from dataclasses import dataclass
from invoke import task
from multiprocessing import Process, Queue
from multiprocessing.queues import Empty as Queue_Empty
from os import makedirs
from os.path import join
from random import uniform
from typing import Dict, List, Tuple, Union
import time
from tasks.util.env import (
    RESULTS_DIR,
)
from tasks.util.openmpi import (
    NATIVE_HOSTFILE,
    get_native_mpi_namespace,
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

WORKLOAD_ALLOWLIST = ["wasm", "native"]
NOT_ENOUGH_SLOTS = "NOT_ENOUGH_SLOTS"
QUEUE_TIMEOUT_SEC = 10
QUEUE_SHUTDOWN = "QUEUE_SHUTDOWN"


def _init_csv_file(workload):
    result_dir = join(RESULTS_DIR, "makespan")
    makedirs(result_dir, exist_ok=True)

    csv_name_makespan = "makespan_{}_time.csv".format(workload)
    csv_name_tiq = "makespan_{}_time_in_queue.csv".format(workload)

    makedirs(RESULTS_DIR, exist_ok=True)
    makespan_file = join(result_dir, csv_name_makespan)
    with open(makespan_file, "w") as out_file:
        out_file.write("NumTasks,Makespan\n")
    tiq_file = join(result_dir, csv_name_tiq)
    with open(tiq_file, "w") as out_file:
        out_file.write("NumTasks,TaskId,TimeInQueue,ExecTime\n")


def _write_line_to_csv(workload, file_name, *args):
    result_dir = join(RESULTS_DIR, "makespan")

    if file_name == "makespan":
        csv_name = "makespan_{}_time.csv".format(workload)
        makespan_file = join(result_dir, csv_name)
        with open(makespan_file, "a") as out_file:
            out_file.write("{},{}\n".format(*args))
    elif file_name == "tiq":
        csv_name = "makespan_{}_time_in_queue.csv".format(workload)
        makespan_file = join(result_dir, csv_name)
        with open(makespan_file, "a") as out_file:
            out_file.write("{},{},{},{}\n".format(*args))
    else:
        raise RuntimeError("Unrecognised file name: {}".format(file_name))


@dataclass
class TaskObject:
    task_id: int
    app: str
    world_size: int


# TODO - maybe move to a different file
def generate_task_trace(
    num_tasks: int, num_cores_per_vm: int
) -> List[TaskObject]:
    possible_world_sizes = [
        int(num_cores_per_vm / 2),
        int(num_cores_per_vm),
        int(num_cores_per_vm * 1.5),
        int(num_cores_per_vm * 2),
    ]
    possible_workloads = ["network", "compute"]

    # Generate the random task trace
    task_trace: List[TaskObject] = []
    num_pos_ws = len(possible_world_sizes)
    num_pos_wl = len(possible_workloads)
    for idx in range(num_tasks):
        ws_idx = int(uniform(0, num_pos_ws))
        wl_idx = int(uniform(0, num_pos_wl))
        task_trace.append(
            TaskObject(
                idx, possible_workloads[wl_idx], possible_world_sizes[ws_idx]
            )
        )

    return task_trace


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
        #         print("Running native task {}/{}:", num + 1, len(tasks))
        #         print("\t- Application: {}".format(tasks[0]))
        #         print("\t- World Size: {}".format(world_size))
        #         print("\t- Master pod: {}".format(tasks[1]))

        # Check for shutdown message
        if work_item.master_pod == QUEUE_SHUTDOWN:
            break

        data_file = get_faasm_benchmark(work_item.task.app)
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
        # exec_output = run_kubectl_cmd("lammps", " ".join(exec_cmd))
        # print(exec_output)
        print(
            "{}: Instead of running the command, sleeping for {} secs".format(
                thread_idx, work_item.task.world_size
            )
        )
        time.sleep(work_item.task.world_size)

        actual_time = int(time.time() - start)

        print(
            "{}: Done sleeping and putting to result queue".format(thread_idx)
        )
        result_queue.put(ResultQueueItem(work_item.task.task_id, actual_time))

    print("Pool thread {} shutting down".format(thread_idx))


class SchedulerState:
    num_vms: int
    num_cores_per_vm: int

    total_slots: int
    total_available_slots: int

    pod_names: List[str]
    pod_map: Dict[str, int] = {}

    in_flight_tasks: Dict[int, List[Tuple[str, int]]] = {}

    def __init__(self, num_vms: int, num_cores_per_vm: int):
        self.num_vms = num_vms
        self.num_cores_per_vm = num_cores_per_vm
        self.total_slots = num_vms * num_cores_per_vm
        self.total_available_slots = self.total_slots

        # Initialise pod names and pod map
        # TODO - eventually different namespace for this experiment
        self.pod_names, _ = get_native_mpi_pods("lammps")
        for pod in self.pod_names:
            self.pod_map[pod] = self.num_cores_per_vm

    def remove_in_flight_task(self, task_id: int) -> None:
        if task_id not in self.in_flight_tasks:
            raise RuntimeError("Task {} not in-flight!".format(task_id))

        # Return the slots to each pod
        scheduling_decision: List[Tuple[str, int]] = self.in_flight_tasks[
            task_id
        ]
        for pod, slots in scheduling_decision:
            self.pod_map[pod] += slots
            self.total_available_slots += slots


class BatchScheduler:
    work_queue: Queue = Queue()
    result_queue: Queue = Queue()
    thread_pool: List[Process]
    state: SchedulerState

    def __init__(self, cluster_dims: List[int], one_task_per_node: bool):
        if len(cluster_dims) != 2:
            print(
                "BatchScheduler expects a two-parameter list as its first"
                "constructor argument: [num_vms, num_cores_per_vm]"
            )
            raise RuntimeError("Incorrect BatchScheduler constructor")

        self.state = SchedulerState(cluster_dims[0], cluster_dims[1])
        self.one_task_per_node = one_task_per_node

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
                "Not enough slots to schedule task {} (needed: {} - have: {})".format(
                    task.task_id,
                    task.world_size,
                    self.state.total_available_slots,
                )
            )
            return NOT_ENOUGH_SLOTS

        scheduling_decision: List[Tuple[str, int]] = []
        left_to_assign: int = task.world_size
        for pod, num_slots in sorted(
            self.state.pod_map.items(), key=lambda item: item[1], reverse=True
        ):
            # Work out how many slots can we take up in this pod
            num_on_this_pod: int = min(num_slots, left_to_assign)
            scheduling_decision.append((pod, num_on_this_pod))

            # Update the global state, and the slots left to assign
            self.state.pod_map[pod] -= num_on_this_pod
            self.state.total_available_slots -= num_on_this_pod
            left_to_assign -= num_on_this_pod

            # If no more slots to assign, exit the loop
            if left_to_assign == 0:
                break
        else:
            print(
                "Ran out of pods to assign task slots to, but still {} to assign".format(
                    left_to_assign
                )
            )
            raise RuntimeError(
                "Scheduling error: inconsistent scheduler state"
            )

        # Before returning, persist the scheduling decision to state
        self.state.in_flight_tasks[task.task_id] = scheduling_decision

        return scheduling_decision

    def execute_native_tasks(
        self, tasks: List[TaskObject]
    ) -> Dict[int, ExecutedTaskInfo]:
        """
        Execute a list of tasks, and return the time it took to run each task.
        Note that for the moment we only measure execution time (not time in
        the queue)
        """
        time_per_task: Dict[int, ExecutedTaskInfo] = {}
        executed_task_count: int = 0

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

                # write to file here

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
                "Scheduling native task {} ({} slots) with master pod {}".format(
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

        return time_per_task

    def run(
        self, workload: str, tasks: List[TaskObject]
    ) -> Dict[int, ExecutedTaskInfo]:
        """
        Main entrypoint to run a number of tasks. The required parameters are:
            - workload: either "native" or "wasm"
            - tasks: a list of TaskObject's
        The method returns a dictionary with timing information to be plotted
        """
        if workload in WORKLOAD_ALLOWLIST:
            print(
                "Batch scheduler received request to execute {} {} tasks".format(
                    len(tasks), workload
                )
            )
        else:
            print("Unrecognised workload type: {}".format(workload))
            print("Allowed workloads are: {}".format(WORKLOAD_ALLOWLIST))
            raise RuntimeError("Unrecognised workload type")

        # Current limitations:
        # - Only "native" workloads
        # - Only LAMMPS apps for native workloads (will need to implement an
        #   equivalent to our migration task)
        if workload == "native":
            return self.execute_native_tasks(tasks)
        else:
            # Flush host here
            raise RuntimeError("WASM workloads still not supported")


@task(default=True)
def run(ctx):
    scheduler = BatchScheduler([4, 4], False)

    # Prepare output files and random task trace
    _init_csv_file("native")
    num_tasks = 10
    task_trace = generate_task_trace(num_tasks, 4)

    makespan_start_time = time.time()
    exec_info = scheduler.run("native", task_trace)
    makespan_time = int(time.time() - makespan_start_time)
    _write_line_to_csv(
        "native", "makespan", num_tasks, makespan_time
    )

    scheduler.shutdown()

    for key in exec_info:
        _write_line_to_csv(
            "native",
            "tiq",
            num_tasks,
            exec_info[key].task_id,
            exec_info[key].time_in_queue,
            exec_info[key].time_executing,
        )
        print(exec_info[key])
