from logging import (
    getLogger,
    INFO as log_level_INFO,
)
from multiprocessing import Process, Queue
from multiprocessing.queues import Empty as Queue_Empty
from os.path import basename
from typing import Dict, List, Tuple, Union
from tasks.lammps.env import (
    LAMMPS_FAASM_USER,
    LAMMPS_FAASM_FUNC,
    get_faasm_benchmark,
)
from tasks.makespan.data import (
    ExecutedTaskInfo,
    ResultQueueItem,
    TaskObject,
    WorkQueueItem,
)
from tasks.makespan.env import (
    LAMMPS_DOCKER_BINARY,
    LAMMPS_DOCKER_DIR,
    LAMMPS_FAASM_MIGRATION_FUNC,
    LAMMPS_MIGRATION_DOCKER_BINARY,
    LAMMPS_MIGRATION_DOCKER_DIR,
    DGEMM_DOCKER_BINARY,
    DGEMM_FAASM_FUNC,
    DGEMM_FAASM_USER,
    MAKESPAN_DIR,
    get_dgemm_cmdline,
)
from tasks.makespan.util import (
    ALLOWED_BASELINES,
    EXEC_TASK_INFO_FILE_PREFIX,
    GRANNY_BASELINES,
    NATIVE_BASELINES,
    SCHEDULINNG_INFO_FILE_PREFIX,
    get_num_cpus_per_vm_from_trace,
    get_workload_from_trace,
    write_line_to_csv,
)
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
    get_faasm_planner_host_port,
    flush_workers as flush_faasm_workers,
    post_async_msg_and_get_result_json,
)
from tasks.util.openmpi import get_native_mpi_pods, run_kubectl_cmd
from time import sleep, time

# Configure a global logger for the scheduler
getLogger("root").setLevel(log_level_INFO)
sch_logger = getLogger("Scheduler")
sch_logger.setLevel(log_level_INFO)


# Useful Constants
NOT_ENOUGH_SLOTS = "NOT_ENOUGH_SLOTS"
QUEUE_TIMEOUT_SEC = 10
QUEUE_SHUTDOWN = "QUEUE_SHUTDOWN"
INTERTASK_SLEEP = 1


def dequeue_with_timeout(
    queue: Queue, queue_str: str, silent: bool = False
) -> Union[ResultQueueItem, WorkQueueItem]:
    while True:
        try:
            result = queue.get(timeout=QUEUE_TIMEOUT_SEC)
            break
        except Queue_Empty:
            if not silent:
                sch_logger.debug(
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
    baseline: str,
    vm_ip_to_name: Dict[str, str],
    num_cpus_per_vm: int,
) -> None:
    """
    Loop for the worker threads in the thread pool. Each thread performs a
    blocking request to execute a task
    """

    def thread_print(msg):
        sch_logger.debug("[Thread {}] {}".format(thread_idx, msg))

    thread_print("Pool thread {} starting".format(thread_idx))

    work_queue: WorkQueueItem
    while True:
        work_item = dequeue_with_timeout(work_queue, "work queue", silent=True)

        # IP for the master VM
        master_vm_ip = work_item.sched_decision[0][0]
        # Check for shutdown message
        if master_vm_ip == QUEUE_SHUTDOWN:
            break
        # Operate with the VM name rather than IP
        master_vm = vm_ip_to_name[master_vm_ip]

        # Choose the right data file if running a LAMMPS simulation
        if work_item.task.app == "mpi" or work_item.task.app == "mpi-migrate":
            # We always use the same LAMMPS benchmark ("compute-xl")
            data_file = get_faasm_benchmark("compute-xl")["data"][0]
            # data_file = get_faasm_benchmark("network")["data"][0]
            # data_file = get_faasm_benchmark("compute")["data"][0]

        # Record the start timestamp
        start_ts = 0
        if baseline in NATIVE_BASELINES:
            if (
                work_item.task.app == "mpi"
                or work_item.task.app == "mpi-migrate"
            ):
                if work_item.task.app == "mpi":
                    binary = LAMMPS_DOCKER_BINARY
                    lammps_dir = LAMMPS_DOCKER_DIR
                elif work_item.task.app == "mpi-migrate":
                    binary = LAMMPS_MIGRATION_DOCKER_BINARY
                    lammps_dir = LAMMPS_MIGRATION_DOCKER_DIR
                native_cmdline = "-in {}/{}.faasm.native".format(
                    lammps_dir, data_file
                )
                world_size = work_item.task.size
                allocated_pod_ips = []
                for tup in work_item.sched_decision:
                    allocated_pod_ips += [tup[0]] * tup[1]

                mpirun_cmd = [
                    "mpirun",
                    "-np {}".format(world_size),
                    # To improve OpenMPI performance, we tell it exactly where
                    # to run each rank. According to the MPI manual, to specify
                    # multiple slots for the same host, we must repeat the host
                    # name. This way, the host string would end up looking like
                    # mpirun -np 5 hostA,hostA,hostA,hostB,hostB ...
                    # https://docs.oracle.com/cd/E19923-01/820-6793-10/ExecutingPrograms.html#50524166_76503
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
            elif work_item.task.app == "omp":
                # TODO(omp): should we set the parallelism level to be
                # min(work_item.task.size, num_slots_per_vm) ? I.e. what will
                # happen when we oversubscribe?
                openmp_cmd = "bash -c '{} {}'".format(
                    DGEMM_DOCKER_BINARY,
                    get_dgemm_cmdline(work_item.task.size),
                )

                exec_cmd = [
                    "exec",
                    master_vm,
                    "--" if backend == "k8s" else "",
                    openmp_cmd,
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
            host, port = get_faasm_planner_host_port()
            url = "http://{}:{}".format(host, port)

            # Prepare Faasm request
            if (
                work_item.task.app == "mpi"
                or work_item.task.app == "mpi-migrate"
            ):
                user = LAMMPS_FAASM_USER
                func = (
                    LAMMPS_FAASM_FUNC
                    if work_item.task.app == "mpi"
                    else LAMMPS_FAASM_MIGRATION_FUNC
                )
                file_name = basename(data_file)
                cmdline = "-in faasm://lammps-data/{}".format(file_name)
                msg = {
                    "user": user,
                    "function": func,
                    "cmdline": cmdline,
                    "mpi": True,
                    "mpi_world_size": work_item.task.size,
                }
                # If attempting to migrate, add a check period
                if work_item.task.app == "mpi-migrate":
                    msg["migration_check_period"] = 5
                    # Do 2 loops, check at the end of loop 1
                    msg["input_data"] = "1 2"
            elif work_item.task.app == "omp":
                if work_item.task.size > num_cpus_per_vm:
                    print(
                        "Requested OpenMP execution with more parallelism"
                        "than slots in the current environment:"
                        "{} > {}".format(work_item.task.size, num_cpus_per_vm)
                    )
                    raise RuntimeError("Error in OpenMP task trace!")
                user = DGEMM_FAASM_USER
                func = "{}_{}".format(DGEMM_FAASM_FUNC, work_item.task.task_id)
                msg = {
                    "user": user,
                    "function": func,
                    # The input_data is the number of OMP threads
                    "cmdline": get_dgemm_cmdline(work_item.task.size),
                }

            start_ts = time()
            # Post asynch request and wait for JSON result
            try:
                result_json = post_async_msg_and_get_result_json(msg, url)
                actual_time = int(get_faasm_exec_time_from_json(result_json))
                thread_print(
                    "Finished executiong app {} (time: {})".format(
                        result_json["appId"], actual_time
                    )
                )
            except RuntimeError:
                actual_time = -1
                sch_logger.error(
                    "Error executing task {}".format(work_item.task.task_id)
                )

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
    # The backend indicates where are we running the experiment. It can either
    # be `k8s` or `compose`
    backend: str
    # The baseline indicate what system are we running. It can be either:
    # `granny`, `batch`, or `slurm`
    baseline: str = ""
    # The trace indicates the experiment we are running. From the trace string
    # we can infer the workload we are running, the number of tasks, and the
    # number of cpus per vm
    trace_str: str
    # The workload indicates the type of application we are runing. It can
    # either be `omp` or `mpi`
    workload: str
    num_tasks: int
    num_cpus_per_vm: int

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
    next_task_in_queue: TaskObject = None

    def __init__(
        self,
        backend: str,
        baseline: str,
        num_tasks: int,
        num_vms: int,
        trace_str: str,
    ):
        self.backend = backend
        self.baseline = baseline
        self.num_tasks = num_tasks
        self.num_vms = num_vms
        self.trace_str = trace_str
        self.num_cpus_per_vm = get_num_cpus_per_vm_from_trace(trace_str)

        # Work-out total number of slots
        self.total_slots = num_vms * self.num_cpus_per_vm
        self.total_available_slots = self.total_slots

        # Initialise the pod list depending on the workload
        self.init_vm_list(backend)

    def init_vm_list(self, backend):
        """
        Initialise pod names and pod map depending on the backend and
        workload
        """
        vm_ips = []
        vm_names = []
        if backend == "compose":
            if self.baseline in NATIVE_BASELINES:
                compose_dir = MAKESPAN_DIR
            else:
                compose_dir = FAASM_ROOT
            vm_names = get_container_names_from_compose(compose_dir)
            vm_ips = get_container_ips_from_compose(compose_dir)
        elif backend == "k8s":
            if self.baseline in NATIVE_BASELINES:
                vm_names, vm_ips = get_native_mpi_pods("makespan")
            else:
                vm_names = get_faasm_worker_pods()
                vm_ips = get_faasm_worker_ips()
        else:
            raise RuntimeError("Unrecognised backend: {}".format(backend))

        # Sanity-check the VM names and IPs we got
        if len(vm_names) != self.num_vms:
            sch_logger.error(
                "ERROR: expected {} VM names, but got {}".format(
                    self.num_vms, len(vm_names)
                )
            )
            sch_logger.info("VM names: {}".format(vm_names))
            raise RuntimeError("Inconsistent scheduler state")
        if len(vm_ips) != self.num_vms:
            sch_logger.error(
                "ERROR: expected {} VM IPs, but got {}".format(
                    self.num_vms, len(vm_ips)
                )
            )
            sch_logger.info("VM IPs: {}".format(vm_ips))
            raise RuntimeError("Inconsistent scheduler state")
        sch_logger.info("Initialised VM Map:")
        for ip, name in zip(vm_ips, vm_names):
            self.vm_map[ip] = self.num_cpus_per_vm
            self.vm_ip_to_name[ip] = name
            sch_logger.info(
                "- IP: {} (name: {}) - Slots: {}".format(
                    ip, name, self.num_cpus_per_vm
                )
            )

    def remove_in_flight_task(self, task_id: int) -> None:
        if task_id not in self.in_flight_tasks:
            raise RuntimeError("Task {} not in-flight!".format(task_id))
        sch_logger.debug(
            "Removing task {} from in-flight tasks".format(task_id)
        )

        # Return the slots to each pod
        scheduling_decision: List[Tuple[str, int]] = self.in_flight_tasks[
            task_id
        ]
        for ip, slots in scheduling_decision:
            self.vm_map[ip] += slots
            self.total_available_slots += slots

    def print_executed_task_info(self, footer_text=None):
        """
        Log the state of the experiment (in particular the state of the
        executed_task_info dictionary). The possible task states are:
        NONE, EXECUTING, FINISHED, and FAILED
        TODO: what about failure?
        """

        # Populate the task array with the task state
        task_state_array = ["NONE" for _ in range(self.num_tasks)]
        for task_id in self.executed_task_info:
            exec_task = self.executed_task_info[task_id]
            if exec_task.time_executing == 0:
                task_state_array[task_id] = "EXECUTING"
            elif exec_task.time_executing == -1:
                task_state_array[task_id] = "FAILED"
            else:
                task_state_array[task_id] = "FINISHED"

        def color_text_from_state(state):
            if state == "NONE":
                return " "
            if state == "EXECUTING":
                return "\033[38;5;3mO\033[0;0m"
            if state == "FINISHED":
                return "\033[38;5;2mX\033[0;0m"
            if state == "FAILED":
                return "\033[38;5;1mX\033[0;0m"

        header = "============ EXPERIMENT STATE ============="
        divider = "--------------------------------------------"
        footer = "==========================================="

        print(header)
        # Print some information on the experiment
        if len(self.backend) <= 3:
            print(
                "Backend: {}\t\tWorkload: {}".format(
                    self.backend, self.baseline
                )
            )
        else:
            print(
                "Backend: {}\tWorkload: {}".format(self.backend, self.baseline)
            )
        print(
            "Num VMs: {}\t\tCores/VM: {}".format(
                len(self.vm_map), self.num_cpus_per_vm
            )
        )
        print(
            "Total cluster occupation: {}/{} ({} %)".format(
                self.total_slots - self.total_available_slots,
                self.total_slots,
                (self.total_slots - self.total_available_slots)
                / self.total_slots
                * 100,
            )
        )
        if self.next_task_in_queue:
            print(
                "Next task in queue: {} (size: {})".format(
                    self.next_task_in_queue.task_id,
                    self.next_task_in_queue.size,
                )
            )
        print(divider)
        # Print it
        tasks_per_line = 10
        line = ""
        for i in range(self.num_tasks):
            color_text = color_text_from_state(task_state_array[i])
            if i == 0:
                line = "{}:  [{}]".format(i, color_text)
            elif i % tasks_per_line == 0:
                print(line)
                line = "{}: [{}]".format(i, color_text)
            else:
                line += " [{}]".format(color_text)
        print(line)
        if footer_text:
            print(divider)
            print(footer_text)
        print(footer)

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
        # Note that we tag CSV files by the hardware we provision; i.e. the
        # number of VMs and the number of cores per VM
        write_line_to_csv(
            self.baseline,
            self.backend,
            EXEC_TASK_INFO_FILE_PREFIX,
            self.num_vms,
            self.trace_str,
            self.executed_task_info[result.task_id].task_id,
            self.executed_task_info[result.task_id].time_executing,
            self.executed_task_info[result.task_id].time_in_queue,
            self.executed_task_info[result.task_id].exec_start_ts,
            self.executed_task_info[result.task_id].exec_end_ts,
        )

        # Lastly, print the executed task info for visualisation purposes
        self.print_executed_task_info()


class BatchScheduler:
    work_queue: Queue = Queue()
    result_queue: Queue = Queue()
    thread_pool: List[Process]
    state: SchedulerState
    start_ts: float = 0.0

    def __init__(
        self,
        backend: str,
        baseline: str,
        num_tasks: int,
        num_vms: int,
        trace_str: str,
    ):
        self.state = SchedulerState(
            backend,
            baseline,
            num_tasks,
            num_vms,
            trace_str,
        )

        print("Initialised batch scheduler with the following parameters:")
        print("\t- Backend: {}".format(backend))
        print("\t- Baseline: {}".format(baseline))
        print("\t- Number of VMs: {}".format(self.state.num_vms))
        print("\t- Cores per VM: {}".format(self.state.num_cpus_per_vm))

        # We are pessimistic with the number of threads and allocate 2 times
        # the number of VMs, as the minimum world size we will ever use is half
        # of a VM
        self.num_threads_in_pool = int(2 * self.state.num_vms)
        self.thread_pool = [
            Process(
                target=thread_pool_thread,
                args=(
                    self.work_queue,
                    self.result_queue,
                    i,
                    backend,
                    baseline,
                    self.state.vm_ip_to_name,
                    self.state.num_cpus_per_vm,
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
            [(QUEUE_SHUTDOWN, -1)], TaskObject(-1, "-1", -1, -1)
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
            sch_logger.info(
                "Not enough slots to schedule task "
                "{}-{} (needed: {} - have: {})".format(
                    task.app,
                    task.task_id,
                    task.size,
                    int(self.state.total_available_slots),
                )
            )
            self.state.next_task_in_queue = task
            return NOT_ENOUGH_SLOTS

        # A scheduling decision is a list of (ip, slots) pairs inidicating
        # how many slots each ip has been assigned for the current task
        scheduling_decision: List[Tuple[str, int]] = []
        left_to_assign = task.size
        # We follow a very simple scheduling policy: we sort the VMs in
        # decresing order of capacity, and schedule as many slots as possible
        # to each VM. We don't distribute OpenMP jobs, as a consequence if
        # the task does not fit the greatest VM, we return
        sorted_vms = sorted(
            self.state.vm_map.items(), key=lambda item: item[1], reverse=True
        )
        # TODO(omp): why should it be any different with OpenMP?
        if task.app == "mpi" or task.app == "mpi-migrate":
            for vm, num_slots in sorted_vms:
                # Work out how many slots can we take up in this pod
                if self.state.baseline == "batch":
                    # The batch native baseline allocates resources at VM
                    # granularity. This means that the current VM should be
                    # empty
                    assert num_slots == self.state.num_cpus_per_vm
                    num_on_this_vm = self.state.num_cpus_per_vm
                else:
                    num_on_this_vm = min(num_slots, left_to_assign)
                scheduling_decision.append((vm, num_on_this_vm))

                # Update the global state, and the slots left to assign
                self.state.vm_map[vm] -= num_on_this_vm
                self.state.total_available_slots -= num_on_this_vm
                left_to_assign -= num_on_this_vm
                sch_logger.debug(
                    "Assigning {} slots to VM {} (left: {})".format(
                        num_on_this_vm, vm, left_to_assign
                    )
                )

                # If no more slots to assign, exit the loop
                if left_to_assign <= 0:
                    break
            else:
                sch_logger.error(
                    "Ran out of pods to assign task slots to, "
                    "but still {} to assign".format(left_to_assign)
                )
                raise RuntimeError(
                    "Scheduling error: inconsistent scheduler state"
                )
        """
        elif task.app == "omp":
            if len(sorted_vms) == 0:
                # TODO: maybe we should raise an inconsistent state error here
                return NOT_ENOUGH_SLOTS
            vm, num_slots = sorted_vms[0]
            if num_slots == 0:
                # TODO: maybe we should raise an inconsistent state error here
                return NOT_ENOUGH_SLOTS
            if self.state.baseline in NATIVE_BASELINES:
                if task.size > self.state.num_cpus_per_vm:
                    print(
                        "Overcomitting for task {} ({} > {})".format(
                            task.task_id,
                            task.size,
                            self.state.num_cpus_per_vm,
                        )
                    )
                num_on_this_vm = self.state.num_cpus_per_vm
            else:
                if num_slots < task.size:
                    return NOT_ENOUGH_SLOTS
                num_on_this_vm = task.size

            scheduling_decision.append((vm, num_on_this_vm))
            self.state.vm_map[vm] -= num_on_this_vm
            # TODO: when we overcommit, do we substract the number of cores
            # we occupy, or the ones we agree to run?
            self.state.total_available_slots -= num_on_this_vm
        """

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
        if self.state.baseline in GRANNY_BASELINES:
            flush_faasm_workers()

        # Mark the initial timestamp
        self.start_ts = time()

        for t in tasks:
            # For the `mpi-migrate` experiment, we don't want the cluster to
            # operate at saturation. As a consequence, we simulate experiment
            # arrivals as a Poisson distribution, and sleep the corresponding
            # inter-arrival time between tasks. For the `mpi` and `omp`
            # experiments, we want the cluster to be saturated, so we ignore
            # the inter-arrival times
            if get_workload_from_trace(self.state.trace_str) == "mpi-migrate":
                sch_logger.debug(
                    "Sleeping {} sec to simulate inter-arrival time...".format(
                        t.inter_arrival_time
                    )
                )
                sleep(t.inter_arrival_time)
                sch_logger.debug("Done sleeping!")
            else:
                sch_logger.debug(
                    "Sleeping {} seconds between tasks".format(INTERTASK_SLEEP)
                )
                sleep(INTERTASK_SLEEP)
                sch_logger.debug("Done sleeping")

            # Try to schedule the task with the current available
            # resources
            scheduling_decision = self.schedule_task_to_vm(t)

            # If we don't have enough resources, wait for results until enough
            # resources, or autoscale if allowed to do so
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
            self.state.print_executed_task_info()

            # Log the scheduling decision
            master_vm = scheduling_decision[0][0]
            sch_logger.debug(
                "Scheduling work task "
                "{} ({} slots) with master VM {}".format(
                    t.task_id, t.size, master_vm
                )
            )
            # Log the scheduling decision to a file
            # TODO: finsih
            write_line_to_csv(
                self.state.baseline,
                self.state.backend,
                SCHEDULINNG_INFO_FILE_PREFIX,
                self.state.num_vms,
                self.state.trace_str,
                t.task_id,
                scheduling_decision,
            )

            # Lastly, put the scheduled task in the work queue
            self.work_queue.put(WorkQueueItem(scheduling_decision, t))

        # Once we are done scheduling tasks, drain the result queue
        while self.state.executed_task_count < len(tasks):
            result = dequeue_with_timeout(self.result_queue, "result queue")

            # Update our local records according to result
            self.state.update_records_from_result(result)

        return self.state.executed_task_info

    def run(
        self, backend: str, baseline: str, tasks: List[TaskObject]
    ) -> Dict[int, ExecutedTaskInfo]:
        """
        Main entrypoint to run a number of tasks scheduled by our batch
        scheduler. The required parameters are:
            - backend: "compose", or "k8s"
            - baseline: "batch", "slurm" or "granny"
            - tasks: a list of TaskObject's
        The method returns a dictionary with timing information to be plotted
        """
        if baseline in ALLOWED_BASELINES:
            print(
                "Batch scheduler received request to execute "
                "{} {} tasks on {}".format(len(tasks), baseline, backend)
            )
            # Initialise the scheduler state and pod list
            self.state.init_vm_list(backend)
            self.num_tasks = len(tasks)
        else:
            print("Unrecognised baseline: {}".format(baseline))
            print("Allowed baselines are: {}".format(ALLOWED_BASELINES))
            raise RuntimeError("Unrecognised baseline")

        return self.execute_tasks(tasks)
