from json import loads as json_loads
from json.decoder import JSONDecodeError
from multiprocessing import Process, Queue
from multiprocessing.queues import Empty as Queue_Empty
from os.path import basename
from pprint import pprint
from requests import post
from typing import Dict, List, Tuple, Union
from tasks.makespan.data import (
    ExecutedTaskInfo,
    ResultQueueItem,
    TaskObject,
    WorkQueueItem,
)
from tasks.makespan.env import MAKESPAN_DIR
from tasks.makespan.util import EXEC_TASK_INFO_FILE_PREFIX, write_line_to_csv
from tasks.util.compose import (
    get_container_names_from_compose,
    get_container_ips_from_compose,
    run_compose_cmd,
)
from tasks.util.env import FAASM_ROOT
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    get_faasm_worker_ips,
    get_faasm_worker_pods,
    get_faasm_invoke_host_port,
    flush_hosts as flush_faasm_hosts,
)
from tasks.util.openmpi import (
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
from time import sleep, time

# Different workloads
WASM_WORKLOADS = ["granny"]
NATIVE_WORKLOADS = ["pc-opt", "uc-opt", "st-opt"]
WORKLOAD_ALLOWLIST = WASM_WORKLOADS + NATIVE_WORKLOADS

# Useful Constants
NOT_ENOUGH_SLOTS = "NOT_ENOUGH_SLOTS"
QUEUE_TIMEOUT_SEC = 10
QUEUE_SHUTDOWN = "QUEUE_SHUTDOWN"


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
    work_queue: Queue,
    result_queue: Queue,
    thread_idx: int,
    backend: str,
    workload: str,
    vm_ip_to_name: Dict[str, str],
    num_slots_per_vm: int,
) -> None:
    """
    Loop for the worker threads in the thread pool. Each thread performs a
    blocking request to execute a task
    """

    def thread_print(msg):
        print("[Thread {}] {}".format(thread_idx, msg))

    thread_print("Pool thread {} starting".format(thread_idx))

    work_queue: WorkQueueItem
    while True:
        work_item = dequeue_with_timeout(work_queue, "work queue", silent=True)

        # IP for the master VM
        master_vm_ip = work_item.allocated_vms[0]
        # Check for shutdown message
        if master_vm_ip == QUEUE_SHUTDOWN:
            break
        # Operate with the VM name rather than IP
        master_vm = vm_ip_to_name[master_vm_ip]

        # Choose the right data file if running a LAMMPS simulation (i.e. not
        # the migration job)
        if work_item.task.app == "mpi":
            # We always use the same LAMMPS benchmark
            data_file = get_faasm_benchmark("compute")["data"][0]
        # TODO(openmp): add the option of openmp here

        # Record the start timestamp
        start_ts = 0
        if workload in NATIVE_WORKLOADS:
            # TODO(openmp): add the option of openmp here
            binary = DOCKER_LAMMPS_BINARY
            native_cmdline = "-in {}/{}.faasm.native".format(
                DOCKER_LAMMPS_DIR, data_file
            )
            world_size = work_item.task.size
            allocated_pod_ips = [
                "{}:{}".format(pn, num_slots_per_vm)
                for pn in work_item.allocated_vms
            ]
            mpirun_cmd = [
                "mpirun",
                "-np {}".format(world_size),
                # To improve OpenMPI performance, we tell it exactly where to
                # run each rank. Could we be more specific about it?
                "-host {}".format(",".join(allocated_pod_ips)),
                binary,
                native_cmdline,
            ]
            mpirun_cmd = " ".join(mpirun_cmd)

            exec_cmd = [
                "exec",
                master_vm,
                "--" if backend == "k8s" else "",
                "su mpirun -c '{}'".format(mpirun_cmd),
            ]
            exec_cmd = " ".join(exec_cmd)

            start_ts = time()
            if backend == "k8s":
                run_kubectl_cmd("makespan", exec_cmd)
            elif backend == "compose":
                run_compose_cmd(thread_idx, MAKESPAN_DIR, exec_cmd)
            actual_time = int(time() - start_ts)
            thread_print("Actual time: {}".format(actual_time))
        else:
            # WASM specific data
            host, port = get_faasm_invoke_host_port()
            url = "http://{}:{}".format(host, port)

            # Prepare Faasm request
            user = LAMMPS_FAASM_USER
            func = LAMMPS_FAASM_FUNC
            file_name = basename(data_file)
            cmdline = "-in faasm://lammps-data/{}".format(file_name)
            msg = {
                "user": user,
                "function": func,
                "cmdline": cmdline,
                "mpi_world_size": work_item.task.size,
                "async": True,
            }
            thread_print("Posting to {} msg:".format(url))
            pprint(msg)

            # Post asynch request
            start_ts = time()
            response = post(url, json=msg, timeout=None)
            # Get the async message id
            if response.status_code != 200:
                thread_print(
                    "Initial request failed: {}:\n{}".format(
                        response.status_code, response.text
                    )
                )
                thread_print("--------------- ERROR ---------------")
                thread_print(
                    "Marking task {} as failed".format(work_item.task.task_id)
                )
                thread_print("-------------------------------------")
                result_queue.put(
                    ResultQueueItem(work_item.task.task_id, -1, time(), time(), "-1")
                )
                continue
            thread_print("Response: {}".format(response.text))
            msg_id = int(response.text.strip())

            # Start polling for the result
            thread_print("Polling message {}".format(msg_id))
            while True:
                interval = 2
                sleep(interval)

                status_msg = {
                    "user": LAMMPS_FAASM_USER,
                    "function": LAMMPS_FAASM_FUNC,
                    "status": True,
                    "id": msg_id,
                }
                response = post(url, json=status_msg)

                if not response.text or response.text.startswith("FAILED"):
                    thread_print("--------------- ERROR ---------------")
                    thread_print(
                        "Marking task {} as failed".format(
                            work_item.task.task_id
                        )
                    )
                    thread_print("-------------------------------------")
                    actual_time = -1
                    break
                elif response.text.startswith("RUNNING"):
                    continue
                else:
                    thread_print("Call finished succesfully")

                # Get the executed time from the response
                try:
                    result_json = json_loads(response.text, strict=False)
                except JSONDecodeError:
                    thread_print("--------------- ERROR ---------------")
                    thread_print(
                        "Marking task {} as failed".format(
                            work_item.task.task_id
                        )
                    )
                    thread_print("-------------------------------------")
                    actual_time = -1
                    break

                actual_time = int(get_faasm_exec_time_from_json(result_json))
                thread_print("Actual time: {}".format(actual_time))

                # Finally exit the polling loop
                break

        result_queue.put(
            ResultQueueItem(
                work_item.task.task_id,
                actual_time,
                start_ts,
                time(),
                master_vm_ip,
            )
        )

    thread_print("Pool thread {} shutting down".format(thread_idx))


class SchedulerState:
    # Variables to identify the experiment being executed
    backend: str
    current_workload: str = ""
    num_vms: int
    num_tasks: int
    num_cores_per_vm: int
    num_users: int

    # Total accounting of slots
    total_slots: int
    total_available_slots: int

    # Bookkeeping of the VMs we have identified by their IP, and their current
    # occupancy
    vm_map: Dict[str, int] = {}
    # Helper map to get the VM name from its IP
    vm_ip_to_name: Dict[str, str] = {}

    # Map of the in-flight tasks in the system. This is, the tasks that are
    # currently being executed. The map's key is the task's id, and the value
    # is the scheduling decision: a list of (ip, cores) pairs with the number
    # of cores assigned to each ip
    in_flight_tasks: Dict[int, List[Tuple[str, int]]] = {}

    # Accounting of the executed tasks and their information
    executed_task_info: Dict[int, ExecutedTaskInfo] = {}
    executed_task_count: int = 0

    def __init__(
        self,
        backend: str,
        current_workload: str,
        num_vms: int,
        num_cores_per_vm: int,
    ):
        self.backend = backend
        self.current_workload = current_workload
        self.num_vms = num_vms
        self.num_cores_per_vm = num_cores_per_vm
        self.total_slots = num_vms * num_cores_per_vm
        self.total_available_slots = self.total_slots

        # Initialise the pod list depending on the workload
        self.init_vm_list(backend)

    def init_vm_list(self, backend):
        # Initialise pod names and pod map depending on the backend and
        # workload
        vm_ips = []
        vm_names = []
        if backend == "compose":
            if self.current_workload in NATIVE_WORKLOADS:
                compose_dir = MAKESPAN_DIR
            else:
                compose_dir = FAASM_ROOT
            vm_names = get_container_names_from_compose(compose_dir)
            vm_ips = get_container_ips_from_compose(compose_dir)
        elif backend == "k8s":
            if self.current_workload in NATIVE_WORKLOADS:
                vm_names, vm_ips = get_native_mpi_pods("makespan")
            else:
                vm_names = get_faasm_worker_pods()
                vm_ips = get_faasm_worker_ips()
        for ip, name in zip(vm_ips, vm_names):
            self.vm_map[ip] = self.num_cores_per_vm
            self.vm_ip_to_name[ip] = name

    def remove_in_flight_task(self, task_id: int) -> None:
        if task_id not in self.in_flight_tasks:
            raise RuntimeError("Task {} not in-flight!".format(task_id))
        print("Removing task {} from in-flight tasks".format(task_id))

        # Return the slots to each pod
        scheduling_decision: List[Tuple[str, int]] = self.in_flight_tasks[
            task_id
        ]
        for ip, slots in scheduling_decision:
            self.vm_map[ip] += slots
            self.total_available_slots += slots

    def update_records_from_result(self, result: ResultQueueItem):
        """
        Given a ResultQueueItem, update our records on executed tasks
        """
        self.remove_in_flight_task(result.task_id)
        if result.task_id not in self.executed_task_info:
            raise RuntimeError("Unrecognised task {}", result.task_id)
        self.executed_task_info[
            result.task_id
        ].time_executing = result.exec_time
        self.executed_task_info[result.task_id].exec_start_ts = result.start_ts
        self.executed_task_info[result.task_id].exec_end_ts = result.end_ts
        self.executed_task_count += 1

        # For reliability, also write a line to a file
        write_line_to_csv(
            self.current_workload,
            self.backend,
            EXEC_TASK_INFO_FILE_PREFIX,
            self.num_vms,
            self.num_tasks,
            self.num_cores_per_vm,
            self.num_users,
            self.executed_task_info[result.task_id].task_id,
            self.executed_task_info[result.task_id].time_executing,
            self.executed_task_info[result.task_id].time_in_queue,
            self.executed_task_info[result.task_id].exec_start_ts,
            self.executed_task_info[result.task_id].exec_end_ts,
        )


class BatchScheduler:
    work_queue: Queue = Queue()
    result_queue: Queue = Queue()
    thread_pool: List[Process]
    state: SchedulerState
    start_ts: float = 0.0

    def __init__(
        self,
        backend: str,
        workload: str,
        num_vms: int,
        num_tasks: int,
        num_slots_per_vm: int,
        num_users: int,
    ):
        self.state = SchedulerState(
            backend, workload, num_vms, num_slots_per_vm
        )
        self.state.backend = backend
        self.state.num_users = num_users
        self.state.num_tasks = num_tasks

        print("Initialised batch scheduler with the following parameters:")
        print("\t- Backend: {}".format(backend))
        print("\t- Workload: {}".format(workload))
        print("\t- Number of VMs: {}".format(self.state.num_vms))
        print("\t- Cores per VM: {}".format(self.state.num_cores_per_vm))

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
                    backend,
                    workload,
                    self.state.vm_ip_to_name,
                    self.state.num_cores_per_vm,
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
        shutdown_msg = WorkQueueItem(
            [QUEUE_SHUTDOWN], TaskObject(-1, "-1", -1, -1, -1)
        )
        for _ in range(self.num_threads_in_pool):
            self.work_queue.put(shutdown_msg)

        for thread in self.thread_pool:
            thread.join()

    # --------- Actual scheduling and accounting -------

    def schedule_task_to_vm(
        self, task: TaskObject
    ) -> Union[str, List[Tuple[str, int]]]:
        if self.state.total_available_slots < task.size:
            # TODO(autoscale): scale up here
            print(
                "Not enough slots to schedule task "
                "{} (needed: {} - have: {})".format(
                    task.task_id,
                    task.size,
                    int(self.state.total_available_slots),
                )
            )
            return NOT_ENOUGH_SLOTS

        # A scheduling decision is a list of (ip, slots) pairs inidicating
        # how many slots each ip has been assigned for the current task
        scheduling_decision: List[Tuple[str, int]] = []
        left_to_assign = task.size
        # We follow a very simple scheduling policy: we sort the VMs in
        # decresing order of capacity, and schedule as many slots as possible
        # to each VM
        for vm, num_slots in sorted(
            self.state.vm_map.items(), key=lambda item: item[1], reverse=True
        ):
            # Work out how many slots can we take up in this pod
            if self.state.current_workload in NATIVE_WORKLOADS:
                # If we are running a native workload we only allow one task
                # per node, which means that regardless of how many slots we
                # have left to assign, we take up all the node. In fact, we
                # should be able to assert that we have the whole VM to
                # allocate
                num_on_this_vm = self.state.num_cores_per_vm
            else:
                num_on_this_vm = min(num_slots, left_to_assign)
            scheduling_decision.append((vm, num_on_this_vm))

            # Update the global state, and the slots left to assign
            self.state.vm_map[vm] -= num_on_this_vm
            self.state.total_available_slots -= num_on_this_vm
            left_to_assign -= num_on_this_vm

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
        # If running a WASM workload, flush the hosts first
        if self.state.current_workload in WASM_WORKLOADS:
            flush_faasm_hosts()

        # Mark the initial timestamp
        self.start_ts = time()

        for t in tasks:
            # First, wait for the inter arrival time
            print(
                "Sleeping {} seconds to simulate inter-arrival time...".format(
                    t.inter_arrival_time
                )
            )
            sleep(t.inter_arrival_time)
            print("Done sleeping!")

            # Try to schedule the task with the current available
            # resources
            scheduling_decision = self.schedule_task_to_vm(t)

            # If we don't have enough resources, wait for results until enough
            # resources, or autoscale if allowed to do so
            # TODO(autoscale)
            time_in_queue_start = time()
            while scheduling_decision == NOT_ENOUGH_SLOTS:
                result: ResultQueueItem

                result = dequeue_with_timeout(
                    self.result_queue, "result queue"
                )

                # Update our local records according to result
                self.state.update_records_from_result(result)

                # Try to schedule again
                scheduling_decision = self.schedule_task_to_vm(t)

            # Once we have been able to schedule the task, record the time it
            # took, i.e. the time the task spent in the queue
            time_in_queue = int(time() - time_in_queue_start)
            self.state.executed_task_info[t.task_id] = ExecutedTaskInfo(
                t.task_id, 0, time_in_queue, 0, 0
            )

            # Log the scheduling decision
            master_vm = scheduling_decision[0][0]
            print(
                "Scheduling native task "
                "{} ({} slots) with master VM {}".format(
                    t.task_id, t.size, master_vm
                )
            )

            # Lastly, put the scheduled task in the work queue
            vms = [it[0] for it in scheduling_decision]
            self.work_queue.put(WorkQueueItem(vms, t))

        # Once we are done scheduling tasks, drain the result queue
        while self.state.executed_task_count < len(tasks):
            result = dequeue_with_timeout(self.result_queue, "result queue")

            # Update our local records according to result
            self.state.update_records_from_result(result)

        return self.state.executed_task_info

    def run(
        self, backend: str, workload: str, tasks: List[TaskObject]
    ) -> Dict[int, ExecutedTaskInfo]:
        """
        Main entrypoint to run a number of tasks scheduled by our batch
        scheduler. The required parameters are:
            - backend: "compose", or "k8s"
            - workload: "native", "batch" or "wasm"
            - tasks: a list of TaskObject's
        The method returns a dictionary with timing information to be plotted
        """
        if workload in WORKLOAD_ALLOWLIST:
            print(
                "Batch scheduler received request to execute "
                "{} {} tasks on {}".format(len(tasks), workload, backend)
            )
            self.state.current_workload = workload
            # Initialise the scheduler state and pod list
            self.state.init_vm_list(backend)
            self.num_tasks = len(tasks)
        else:
            print("Unrecognised workload type: {}".format(workload))
            print("Allowed workloads are: {}".format(WORKLOAD_ALLOWLIST))
            raise RuntimeError("Unrecognised workload type")

        return self.execute_tasks(tasks)
