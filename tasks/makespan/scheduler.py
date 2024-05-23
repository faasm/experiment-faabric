from faasmctl.util.config import (
    get_faasm_worker_ips,
    get_faasm_worker_names,
)
from faasmctl.util.planner import (
    get_in_fligh_apps as planner_get_in_fligh_apps,
    set_next_evicted_host as planner_set_next_evicted_host,
    wait_for_workers as planner_wait_for_workers,
)
from faasmctl.util.restart import replica as restart_faasm_replica
from logging import (
    getLogger,
    INFO as log_level_INFO,
)
from multiprocessing import Process, Queue
from multiprocessing.queues import Empty as Queue_Empty
from os.path import basename
from random import sample
from subprocess import CalledProcessError
from typing import Dict, List, Tuple, Union
from tasks.makespan.data import (
    ExecutedTaskInfo,
    ResultQueueItem,
    TaskObject,
    WorkQueueItem,
)
from tasks.util.elastic import (
    ELASTIC_KERNEL,
    OPENMP_ELASTIC_FUNCTION,
    OPENMP_ELASTIC_NATIVE_BINARY,
    OPENMP_ELASTIC_USER,
    get_elastic_input_data,
)
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    has_app_failed,
    post_async_msg_and_get_result_json,
)
from tasks.util.kernels import get_openmp_kernel_cmdline
from tasks.util.k8s import wait_for_pods as wait_for_native_mpi_pods
from tasks.util.lammps import (
    LAMMPS_FAASM_USER,
    LAMMPS_DOCKER_BINARY,
    LAMMPS_DOCKER_DIR,
    LAMMPS_FAASM_MIGRATION_NET_FUNC,
    LAMMPS_MIGRATION_NET_DOCKER_BINARY,
    LAMMPS_MIGRATION_NET_DOCKER_DIR,
    LAMMPS_SIM_NUM_ITERATIONS,
    get_lammps_data_file,
    get_lammps_migration_params,
    get_lammps_workload,
)
from tasks.util.makespan import (
    ALLOWED_BASELINES,
    EXEC_TASK_INFO_FILE_PREFIX,
    GRANNY_BASELINES,
    GRANNY_BATCH_BASELINES,
    GRANNY_ELASTIC_BASELINES,
    GRANNY_FT_BASELINES,
    GRANNY_MIGRATE_BASELINES,
    MPI_MIGRATE_WORKLOADS,
    MPI_WORKLOADS,
    NATIVE_BASELINES,
    NATIVE_FT_BASELINES,
    OPENMP_WORKLOADS,
    SCHEDULING_INFO_FILE_PREFIX,
    get_num_cpus_per_vm_from_trace,
    get_user_id_from_task,
    get_workload_from_trace,
    write_line_to_csv,
)
from tasks.util.openmpi import (
    get_native_mpi_namespace,
    get_native_mpi_pods,
    restart_native_mpi_pod,
    run_kubectl_cmd,
)
from tasks.util.planner import (
    get_num_available_slots_from_in_flight_apps,
    get_num_idle_cpus_from_in_flight_apps,
    get_num_xvm_links_from_in_flight_apps,
)
from time import sleep, time

ALL_FT_BASELINES = GRANNY_FT_BASELINES + NATIVE_FT_BASELINES

# Configure a global logger for the scheduler
getLogger("root").setLevel(log_level_INFO)
sch_logger = getLogger("Scheduler")
sch_logger.setLevel(log_level_INFO)


# Useful Constants
NOT_ENOUGH_SLOTS = "NOT_ENOUGH_SLOTS"
QUEUE_TIMEOUT_SEC = 10
QUEUE_SHUTDOWN = "QUEUE_SHUTDOWN"
INTERTASK_SLEEP = 1
# How often do we query the planner for cluster occupation
PLANNER_MONITOR_RESOLUTION_SECS = 4


def has_task_failed(result: ResultQueueItem):
    return result.exec_time == -1


def fault_injection_thread(
    baseline,
    num_vms,
    fault_injection_period_secs,
    host_grace_period_secs,
    num_faults,
):
    """
    Thread used to periodically inject faults in a running cluster

    The two arguments after the baseline determine the profile of our spot VM
    simulation. The grace period value we get from Azure's reference, and the
    FT period we make up. We could consider changing them but, for simplicity
    we keep them the same
    """

    def get_next_evicted_host(baseline, num_hosts_to_evict):
        if baseline in GRANNY_BASELINES:
            vm_names = get_faasm_worker_names()
            vm_ips = get_faasm_worker_ips()
        else:
            vm_names, vm_ips = get_native_mpi_pods("makespan")

        assert (
            len(vm_names) == num_vms
        ), "Mismatch in FT thread picking next evicted host {} != {}".format(
            num_vms, len(vm_names)
        )

        evicted_idxs = sample(range(0, len(vm_names)), num_hosts_to_evict)
        evicted_vm_names = [
            vm_names[evicted_idx] for evicted_idx in evicted_idxs
        ]
        evicted_vm_ips = [vm_ips[evicted_idx] for evicted_idx in evicted_idxs]

        return evicted_vm_names, evicted_vm_ips

    # Main fault-injection loop. We have two periods that determine the loop:
    # (i) how often we inject a fault, and (ii) how much heads-up we give the
    # batch-scheduler (grace period). In the loop, we first sleep for (i) -
    # (ii) and then for (ii)
    while True:
        next_evicted_hosts, next_evicted_ips = get_next_evicted_host(
            baseline, num_faults
        )

        # First, sleep until we need to give the grace period
        sleep(fault_injection_period_secs - host_grace_period_secs)

        # Then, notify that the host will be evicted (only Granny understands
        # this)
        if baseline in GRANNY_BASELINES:
            planner_set_next_evicted_host(next_evicted_ips)

        # Now sleep for the grace period
        sleep(host_grace_period_secs)

        # Finally, restart the host to simulate a spot VM eviction (aka fault)
        if baseline in GRANNY_BASELINES:
            restart_faasm_replica(next_evicted_hosts)

            # Wait for workers to be ready
            planner_wait_for_workers(num_vms)
        else:
            restart_native_mpi_pod("makespan", next_evicted_hosts)


def dequeue_with_timeout(
    queue: Queue,
    queue_str: str,
    silent: bool = False,
    throw: bool = False,
    timeout_s: int = QUEUE_TIMEOUT_SEC,
) -> Union[ResultQueueItem, WorkQueueItem]:
    while True:
        try:
            result = queue.get(timeout=timeout_s)
            break
        except Queue_Empty:
            if throw:
                raise Queue_Empty
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
    baseline: str,
    num_vms: int,
    num_cpus_per_vm: int,
    num_tasks_per_user: int,
    trace_str: str,
) -> None:
    """
    Loop for the worker threads in the thread pool. Each thread performs a
    blocking request to execute a task
    """

    def thread_print(msg):
        sch_logger.debug("[Thread {}] {}".format(thread_idx, msg))

    thread_print("Pool thread {} starting".format(thread_idx))

    if thread_idx == 0:
        if baseline in NATIVE_BASELINES:
            return

        read_one = False
        while True:
            sleep(PLANNER_MONITOR_RESOLUTION_SECS)

            in_flight_apps = planner_get_in_fligh_apps()
            idle_vms, idle_cpus = get_num_idle_cpus_from_in_flight_apps(
                num_vms,
                num_cpus_per_vm,
                in_flight_apps,
            )

            if read_one and len(in_flight_apps.apps) == 0:
                print("Zero in-flight apps. Shutting down poller thread...")
                break
            elif len(in_flight_apps.apps) != 0:
                read_one = True

            write_line_to_csv(
                baseline,
                SCHEDULING_INFO_FILE_PREFIX,
                num_vms,
                num_tasks_per_user,
                trace_str,
                time(),
                idle_vms,
                idle_cpus,
                get_num_xvm_links_from_in_flight_apps(in_flight_apps),
            )

    work_queue: WorkQueueItem
    while True:
        work_item = dequeue_with_timeout(work_queue, "work queue", silent=True)
        has_failed = False

        # IP for the master VM
        master_vm_ip = None
        if len(work_item.sched_decision) > 0:
            master_vm_ip = work_item.sched_decision[0][0]

        if baseline in NATIVE_BASELINES and master_vm_ip != QUEUE_SHUTDOWN:
            # Get the VM name for an IP directly from kuberenetes every
            # time, as the translation may become stale in a faulty
            # workload (e.g. mpi-spot)
            names, ips = get_native_mpi_pods("makespan")
            for name, ip in zip(names, ips):
                if ip == master_vm_ip:
                    master_vm = name

        # Check for shutdown message
        if master_vm_ip == QUEUE_SHUTDOWN:
            break

        # Choose the right data file if running a LAMMPS simulation
        if work_item.task.app in MPI_WORKLOADS:
            if work_item.task.app == "mpi-locality":
                lammps_workload = "very-network"
            else:
                lammps_workload = "compute"

            workload_config = get_lammps_workload(lammps_workload)
            assert (
                "data_file" in workload_config
            ), "Workload config has no data file!"
            data_file = get_lammps_data_file(workload_config["data_file"])[
                "data"
            ][0]

        # Record the start timestamp
        start_ts = 0
        if baseline in NATIVE_BASELINES:
            if work_item.task.app in MPI_WORKLOADS:
                if work_item.task.app == "mpi":
                    binary = LAMMPS_DOCKER_BINARY
                    lammps_dir = LAMMPS_DOCKER_DIR
                elif work_item.task.app in MPI_MIGRATE_WORKLOADS:
                    binary = LAMMPS_MIGRATION_NET_DOCKER_BINARY
                    lammps_dir = LAMMPS_MIGRATION_NET_DOCKER_DIR
                native_cmdline = "-in {}/{}.faasm.native".format(
                    lammps_dir, data_file
                )
                world_size = work_item.task.size
                allocated_pod_ips = []
                for tup in work_item.sched_decision:
                    allocated_pod_ips += [tup[0]] * tup[1]

                mpirun_cmd = [
                    "mpirun",
                    get_lammps_migration_params(
                        num_loops=workload_config["num_iterations"],
                        num_net_loops=workload_config["num_net_loops"],
                        chunk_size=workload_config["chunk_size"],
                        native=True,
                    ),
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
                    "--",
                    "su mpirun -c '{}'".format(mpirun_cmd),
                ]
                exec_cmd = " ".join(exec_cmd)
            elif work_item.task.app in OPENMP_WORKLOADS:
                openmp_cmd = "bash -c '{} {} {}'".format(
                    get_elastic_input_data(native=True),
                    OPENMP_ELASTIC_NATIVE_BINARY,
                    get_openmp_kernel_cmdline(
                        ELASTIC_KERNEL, work_item.task.size
                    ),
                )

                exec_cmd = [
                    "exec",
                    master_vm,
                    "--",
                    openmp_cmd,
                ]
                exec_cmd = " ".join(exec_cmd)

            start_ts = time()
            try:
                run_kubectl_cmd("makespan", exec_cmd)
            except CalledProcessError:
                has_failed = True
            actual_time = int(time() - start_ts)
        else:
            # Prepare Faasm request
            req = {}

            if work_item.task.app in MPI_WORKLOADS:
                user = LAMMPS_FAASM_USER
                func = LAMMPS_FAASM_MIGRATION_NET_FUNC
                file_name = basename(data_file)
                cmdline = "-in faasm://lammps-data/{}".format(file_name)

                req["user"] = user
                req["function"] = func
                if get_workload_from_trace(trace_str) == "mpi-evict":
                    req["subType"] = get_user_id_from_task(
                        num_tasks_per_user, work_item.task.task_id
                    )

                msg = {
                    "user": user,
                    "function": func,
                    "cmdline": cmdline,
                    "mpi": True,
                    "mpi_world_size": work_item.task.size,
                }

                # If attempting to migrate, add migration parameters
                baselines_with_migration = (
                    GRANNY_MIGRATE_BASELINES + GRANNY_FT_BASELINES
                )
                if work_item.task.app in MPI_MIGRATE_WORKLOADS:
                    check_every = (
                        1
                        if baseline in baselines_with_migration
                        else LAMMPS_SIM_NUM_ITERATIONS
                    )
                    msg["input_data"] = get_lammps_migration_params(
                        check_every=check_every,
                        num_loops=workload_config["num_iterations"],
                        num_net_loops=workload_config["num_net_loops"],
                        chunk_size=workload_config["chunk_size"],
                    )
            elif work_item.task.app in OPENMP_WORKLOADS:
                if work_item.task.size > num_cpus_per_vm:
                    print(
                        "Requested OpenMP execution with more parallelism"
                        "than slots in the current environment:"
                        "{} > {}".format(work_item.task.size, num_cpus_per_vm)
                    )
                    raise RuntimeError("Error in OpenMP task trace!")
                user = OPENMP_ELASTIC_USER
                func = OPENMP_ELASTIC_FUNCTION
                msg = {
                    "user": user,
                    "function": func,
                    "input_data": get_elastic_input_data(),
                    "cmdline": get_openmp_kernel_cmdline(
                        ELASTIC_KERNEL, work_item.task.size
                    ),
                    "isOmp": True,
                    "ompNumThreads": work_item.task.size,
                }

                req["user"] = user
                req["function"] = func
                req["singleHostHint"] = True
                req["elasticScaleHint"] = baseline in GRANNY_ELASTIC_BASELINES

            # Post asynch request and wait for JSON result
            start_ts = time()
            result_json = post_async_msg_and_get_result_json(msg, req_dict=req)
            actual_time = int(get_faasm_exec_time_from_json(result_json))
            has_failed = has_app_failed(result_json)
            thread_print(
                "Finished executiong app {} (time: {})".format(
                    result_json[0]["appId"], actual_time
                )
            )

        end_ts = time()

        if has_failed:
            sch_logger.error(
                "Error executing task {}".format(work_item.task.task_id)
            )
            result_queue.put(
                ResultQueueItem(
                    work_item.task.task_id,
                    -1,
                    -1,
                    -1,
                    master_vm_ip,
                )
            )
        else:
            result_queue.put(
                ResultQueueItem(
                    work_item.task.task_id,
                    actual_time,
                    start_ts,
                    end_ts,
                    master_vm_ip,
                )
            )

    thread_print("Pool thread {} shutting down".format(thread_idx))


class SchedulerState:
    # The baseline indicate what system are we running. It can be either:
    # `granny`, `batch`, or `slurm`
    baseline: str = ""
    # The trace indicates the experiment we are running. From the trace string
    # we can infer the workload we are running, the number of tasks, and the
    # number of cpus per vm
    trace_str: str
    # The workload indicates the type of application we are runing. It can
    # either be `omp-elastic` or `mpi-migrate` or `mpi-evict` or `mpi-spot`
    workload: str
    num_tasks: int
    num_cpus_per_vm: int
    num_tasks_per_user: int
    # Only for `mpi-spot`, number of faulty VMs
    num_faults: int = 0

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
        baseline: str,
        num_tasks: int,
        num_vms: int,
        num_tasks_per_user: int,
        trace_str: str,
    ):
        self.baseline = baseline
        self.num_tasks = num_tasks
        self.num_vms = num_vms
        self.num_tasks_per_user = num_tasks_per_user
        self.trace_str = trace_str
        self.num_cpus_per_vm = get_num_cpus_per_vm_from_trace(trace_str)
        self.workload = get_workload_from_trace(trace_str)

        # Work-out total number of slots
        self.total_slots = num_vms * self.num_cpus_per_vm
        self.total_available_slots = self.total_slots

        # Initialise the pod list depending on the workload
        self.init_vm_list()

    def init_vm_list(self):
        """
        Initialise pod names and pod map depending on the baseline
        """
        if self.baseline in NATIVE_BASELINES:
            vm_names, vm_ips = get_native_mpi_pods("makespan")
        else:
            vm_names = get_faasm_worker_names()
            vm_ips = get_faasm_worker_ips()

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

    def update_vm_list(self):
        if self.baseline not in NATIVE_BASELINES:
            raise RuntimeError(
                "This method should only be used in native baselines!"
            )

        wait_for_native_mpi_pods(
            get_native_mpi_namespace("makespan"),
            "run=faasm-openmpi",
            num_expected=self.num_vms,
            quiet=True,
        )
        vm_names, vm_ips = get_native_mpi_pods("makespan")

        # First, delete the IPs that are not in the cluster anymore
        ips_to_delete = []
        for vm_ip in self.vm_map:
            if vm_ip not in vm_ips:
                ips_to_delete.append(vm_ip)

        for vm_ip in ips_to_delete:
            del self.vm_map[vm_ip]
            del self.vm_ip_to_name[vm_ip]

        # Second, add the new IPs
        for vm_ip, vm_name in zip(vm_ips, vm_names):
            if vm_ip not in self.vm_map:
                self.vm_map[vm_ip] = self.num_cpus_per_vm
                self.vm_ip_to_name[vm_ip] = vm_name

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
            if ip in self.vm_map:
                self.vm_map[ip] += slots

            self.total_available_slots += slots

        # Remove the task from in-flight
        del self.in_flight_tasks[task_id]

    def get_next_task(self, tasks):
        for task in tasks:
            if (
                task.task_id in self.executed_task_info
                and self.executed_task_info[task.task_id].time_executing == -1
            ):
                return task

            if task.task_id not in self.executed_task_info:
                return task

        return None

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
        print(
            "Wload: {}\tNum VMs: {}\tCores/VM: {}".format(
                self.baseline, len(self.vm_map), self.num_cpus_per_vm
            )
        )
        print(
            "Total cluster occupation: {}/{} ({:.2f} %)".format(
                self.total_slots - self.total_available_slots,
                self.total_slots,
                (self.total_slots - self.total_available_slots)
                / self.total_slots
                * 100,
            )
        )
        if self.next_task_in_queue is not None:
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

        if not has_task_failed(result):
            self.executed_task_count += 1

            # For reliability, also write a line to a file
            # Note that we tag CSV files by the hardware we provision; i.e. the
            # number of VMs and the number of cores per VM
            write_line_to_csv(
                self.baseline,
                EXEC_TASK_INFO_FILE_PREFIX,
                self.num_vms,
                self.num_tasks_per_user,
                self.trace_str,
                self.executed_task_info[result.task_id].task_id,
                self.executed_task_info[result.task_id].time_executing,
                self.executed_task_info[result.task_id].time_in_queue,
                self.executed_task_info[result.task_id].exec_start_ts,
                self.executed_task_info[result.task_id].exec_end_ts,
            )

        # Lastly, print the executed task info for visualisation purposes
        self.print_executed_task_info()

        # For native baselines that rely on this scheduler for the correct IP
        # allocation, we need to update the list of IPs and VM map
        if self.baseline in NATIVE_BASELINES:
            self.update_vm_list()


class BatchScheduler:
    work_queue: Queue = Queue()
    result_queue: Queue = Queue()
    thread_pool: List[Process]
    state: SchedulerState
    start_ts: float = 0.0
    fault_injection_daemon: Process

    def __init__(
        self,
        baseline: str,
        num_tasks: int,
        num_vms: int,
        num_tasks_per_user: int,
        trace_str: str,
    ):
        self.state = SchedulerState(
            baseline,
            num_tasks,
            num_vms,
            num_tasks_per_user,
            trace_str,
        )

        print("Initialised batch scheduler with the following parameters:")
        print("\t- Baseline: {}".format(baseline))
        print("\t- Workload: {}".format(self.state.workload))
        print("\t- Number of VMs: {}".format(self.state.num_vms))
        print("\t- Cores per VM: {}".format(self.state.num_cpus_per_vm))

        # We are pessimistic with the number of threads and allocate 2 times
        # the number of VMs, as the minimum world size we will ever use is half
        # of a VM. We use and additional thread to monitor the number of cross-
        # VM links in our deployment
        self.num_threads_in_pool = int(2 * self.state.num_vms + 1)
        self.thread_pool = [
            Process(
                target=thread_pool_thread,
                args=(
                    self.work_queue,
                    self.result_queue,
                    i,
                    baseline,
                    self.state.num_vms,
                    self.state.num_cpus_per_vm,
                    self.state.num_tasks_per_user,
                    self.state.trace_str,
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

        # Start the fault injection daemon for the appropriate workloads
        if self.state.workload == "mpi-spot" and baseline in ALL_FT_BASELINES:
            # How often we notify a host that it will be evicted
            fault_injection_period_secs = 60
            # What grace period do we give hosts after notifying their eviction
            host_grace_period_secs = 60
            # How many faults we are injecting
            num_faults = int(num_vms / 4)
            self.state.num_faults = num_faults

            self.fault_injection_daemon = Process(
                target=fault_injection_thread,
                daemon=True,
                args=(
                    baseline,
                    self.state.num_vms,
                    fault_injection_period_secs,
                    host_grace_period_secs,
                    num_faults,
                ),
            )
            self.fault_injection_daemon.start()

            print("Initialised background fault-injection thread")

    def shutdown(self):
        shutdown_msg = WorkQueueItem(
            [(QUEUE_SHUTDOWN, -1)], TaskObject(-1, "-1", -1, -1)
        )
        for _ in range(self.num_threads_in_pool):
            self.work_queue.put(shutdown_msg)

        for thread in self.thread_pool:
            thread.join()

    # --------- Actual scheduling and accounting -------

    # In a multi-tenant setting, we want to _not_ consider for scheduling nodes
    # that are already running tasks for different users
    def prune_node_list_from_different_users(self, nodes, this_task):
        this_task_id = get_user_id_from_task(
            self.state.num_tasks_per_user, this_task.task_id
        )

        def get_indx_in_list(node_list, host_ip):
            for idx, pair in enumerate(node_list):
                if pair[0] == host_ip:
                    return idx

            return -1

        for task_id in self.state.in_flight_tasks:
            if (
                get_user_id_from_task(self.state.num_tasks_per_user, task_id)
                == this_task_id
            ):
                continue

            sched_decision = self.state.in_flight_tasks[task_id]
            for host_ip, num_msgs_in_host in sched_decision:
                idx = get_indx_in_list(nodes, host_ip)
                if idx != -1:
                    del nodes[idx]

        return nodes

    def num_available_slots_from_vm_list(self, vm_list):
        num_avail_slots = 0

        for vm, num_slots in vm_list:
            num_avail_slots += num_slots

        return num_avail_slots

    # Helper method to know if we have enough slots to schedule a task
    def have_enough_slots_for_task(self, task: TaskObject):
        if self.state.baseline in NATIVE_BASELINES:
            if self.state.workload == "mpi-evict":
                # For `mpi-evict` we run a multi-tenant trace, and prevent apps
                # from different users from running in the same VM
                sorted_vms = sorted(
                    self.state.vm_map.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )

                pruned_vms = self.prune_node_list_from_different_users(
                    sorted_vms, task
                )

                return (
                    self.num_available_slots_from_vm_list(pruned_vms)
                    >= task.size
                )
            elif self.state.workload in OPENMP_WORKLOADS:
                # For OpenMP workloads, we can only allocate them in one VM, so
                # we compare the requested size with the largest capacity we
                # have in one VM
                sorted_vms = sorted(
                    self.state.vm_map.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )

                return sorted_vms[0][1] >= task.size
            else:
                return self.state.total_available_slots >= task.size
        else:
            # For Granny, we can always rely on the planner to let us know
            # how many slots we can use
            if self.state.workload == "mpi-evict":
                return (
                    get_num_available_slots_from_in_flight_apps(
                        self.state.num_vms,
                        self.state.num_cpus_per_vm,
                        user_id=get_user_id_from_task(
                            self.state.num_tasks_per_user, task.task_id
                        ),
                    )
                    >= task.size
                )

            if (
                self.state.workload == "mpi-spot"
                and self.state.baseline in GRANNY_FT_BASELINES
            ):
                return (
                    get_num_available_slots_from_in_flight_apps(
                        self.state.num_vms,
                        self.state.num_cpus_per_vm,
                        num_evicted_vms=self.state.num_faults,
                    )
                    >= task.size
                )

            if (
                self.state.workload == "mpi-locality"
                and self.state.baseline in GRANNY_MIGRATE_BASELINES
            ):
                return (
                    get_num_available_slots_from_in_flight_apps(
                        self.state.num_vms,
                        self.state.num_cpus_per_vm,
                        next_task_size=task.size,
                    )
                    >= task.size
                )

            if (
                self.state.workload == "mpi-locality"
                and self.state.baseline in GRANNY_BATCH_BASELINES
            ):
                return (
                    get_num_available_slots_from_in_flight_apps(
                        self.state.num_vms,
                        self.state.num_cpus_per_vm,
                        next_task_size=task.size,
                        batch=True,
                    )
                    >= task.size
                )

            if self.state.workload in OPENMP_WORKLOADS:
                return (
                    get_num_available_slots_from_in_flight_apps(
                        self.state.num_vms,
                        self.state.num_cpus_per_vm,
                        openmp=True,
                    )
                    >= task.size
                )

            return (
                get_num_available_slots_from_in_flight_apps(
                    self.state.num_vms, self.state.num_cpus_per_vm
                )
                >= task.size
            )

    def schedule_task_to_vm(
        self, task: TaskObject
    ) -> Union[str, List[Tuple[str, int]]]:
        if not self.have_enough_slots_for_task(task):
            sch_logger.info(
                "Not enough slots to schedule task "
                "{}-{} (needed: {} - have: {})".format(
                    task.app,
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
        # to each VM. We don't distribute OpenMP jobs, as a consequence if
        # the task does not fit the greatest VM, we return
        sorted_vms = sorted(
            self.state.vm_map.items(), key=lambda item: item[1], reverse=True
        )

        if self.state.workload == "mpi-evict":
            sorted_vms = self.prune_node_list_from_different_users(
                sorted_vms, task
            )

        if self.state.workload in OPENMP_WORKLOADS:
            sorted_vms = [sorted_vms[0]]

        # For GRANNY baselines we can skip the python-side accounting as the
        # planner has all the scheduling information
        if self.state.baseline in NATIVE_BASELINES:
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

        # Before returning, persist the scheduling decision to state
        self.state.in_flight_tasks[task.task_id] = scheduling_decision

        return scheduling_decision

    def execute_tasks(
        self, tasks: List[TaskObject]
    ) -> Dict[int, ExecutedTaskInfo]:
        """
        Execute a list of tasks, and return details on the task execution
        """
        # Mark the initial timestamp
        self.start_ts = time()

        # def do_execute_tasks(this_tasks):

        # We loop through all the tasks in a while loop to make sure that we
        # re-start tasks that have failed
        while True:
            # for t_num, t in enumerate(this_tasks):
            t = self.state.get_next_task(tasks)

            while t is not None:
                sch_logger.debug(
                    "Sleeping {} seconds between tasks".format(INTERTASK_SLEEP)
                )
                sleep(INTERTASK_SLEEP)
                sch_logger.debug("Done sleeping")

                # Try to schedule the task with the current available
                # resources
                scheduling_decision = self.schedule_task_to_vm(t)

                # If we don't have enough resources, wait for results until enough
                # resources
                time_in_queue_start = time()
                while scheduling_decision == NOT_ENOUGH_SLOTS:
                    result: ResultQueueItem

                    # In the MPI evict baseline we want to query often about being
                    # able to schedule, as some planner migrations may unblock
                    # scheduling
                    if (
                        self.state.workload == "mpi-evict"
                        and self.state.baseline in GRANNY_BASELINES
                    ):
                        # If there are not enough slots, first try to deque
                        try:
                            result = dequeue_with_timeout(
                                self.result_queue,
                                "result queue",
                                throw=True,
                                timeout_s=1,
                            )

                            # If dequeue works, update records and try to
                            # schedule again
                            self.state.update_records_from_result(result)
                        except Queue_Empty:
                            # If dequeue does not work (it times out) try to
                            # schedule again anyway
                            pass

                        scheduling_decision = self.schedule_task_to_vm(t)
                    else:
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

                # Log the scheduling decision to a file
                if self.state.baseline in NATIVE_BASELINES:
                    write_line_to_csv(
                        self.state.baseline,
                        SCHEDULING_INFO_FILE_PREFIX,
                        self.state.num_vms,
                        self.state.num_tasks_per_user,
                        self.state.trace_str,
                        t.task_id,
                        scheduling_decision,
                    )

                # Lastly, put the scheduled task in the work queue
                self.work_queue.put(WorkQueueItem(scheduling_decision, t))

                t = self.state.get_next_task(tasks)

                # Before printing the executed task info, update the next task
                # (so that it is not anymore the current one)
                if t is not None:
                    self.state.next_task_in_queue = t
                self.state.print_executed_task_info()

            # Once we are done scheduling tasks, drain the result queue (no more
            # tasks are next in queue). If any of the dequeued tasks fails,
            # we will go back to the beginning
            self.state.next_task_in_queue = None
            while self.state.executed_task_count < len(tasks):
                result = dequeue_with_timeout(
                    self.result_queue, "result queue"
                )

                # Update our local records according to result
                self.state.update_records_from_result(result)

                # If the task has failed, make sure we try to run it again
                if has_task_failed(result):
                    break

            # Finally, break out of the main loop if we are indeed done
            if self.state.executed_task_count == len(tasks):
                break

        return self.state.executed_task_info

    def run(
        self, baseline: str, tasks: List[TaskObject]
    ) -> Dict[int, ExecutedTaskInfo]:
        """
        Main entrypoint to run a number of tasks scheduled by our batch
        scheduler. The required parameters are:
            - baseline: "batch", "slurm" or "granny"
            - tasks: a list of TaskObject's
        The method returns a dictionary with timing information to be plotted
        """
        if baseline in ALLOWED_BASELINES:
            print(
                "Batch scheduler received request to execute "
                "{} {} tasks".format(len(tasks), baseline)
            )
            # Initialise the scheduler state and pod list
            self.state.init_vm_list()
            self.num_tasks = len(tasks)
        else:
            print("Unrecognised baseline: {}".format(baseline))
            print("Allowed baselines are: {}".format(ALLOWED_BASELINES))
            raise RuntimeError("Unrecognised baseline")

        return self.execute_tasks(tasks)
