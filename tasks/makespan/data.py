from dataclasses import dataclass
from typing import List

"""
This file stores the definitions of the different data structures used in the
makespan experiment, mostly as part of our implementation of different batch
schedulers.
"""


@dataclass
class TaskObject:
    """
    One task (or job) of an experiment. Each task is identified by:
    - task_id: unique identifier of the task
    - app: type of workload the task is running, one in: `mpi` or `openmp`
    - size: task's requirements in terms of CPUs
    - inter_arrival_time: delay in seconds for the task to arrive wrt the
        previous task
    - user_id: identifier of the user the task belongs to
    """

    task_id: int
    app: str
    size: int
    inter_arrival_time: int
    user_id: int


@dataclass
class ExecutedTaskInfo:
    """
    Information about an executed task for plotting and analysis
    """

    task_id: int
    # Times are in seconds and rounded to zero decimal places
    time_executing: float
    time_in_queue: float
    # Timestamps for when the task starts and finishes executing
    exec_start_ts: float
    exec_end_ts: float


@dataclass
class ResultQueueItem:
    """
    Item of the result queue where task results are stored
    """

    task_id: int
    exec_time: float
    start_ts: float
    end_ts: float
    master_ip: str


@dataclass
class WorkQueueItem:
    """
    Item of the work queue scheduler threads consume
    """
    # List of VM IPs allocated for this task
    allocated_vms: List[str]
    task: TaskObject
