from invoke import task
from signal import signal, SIGINT
from sys import exit
from tasks.util.faasm import get_faasm_planner_host_port
from tasks.util.planner import print_planner_resources
from time import sleep


@task
def monitor(ctx):
    """
    Monitor the planner resources
    """
    host, port = get_faasm_planner_host_port()

    def sigint_handler(sig, frame):
        print("Stopping monitoring...")
        exit(0)

    signal(SIGINT, sigint_handler)

    print("Starting monitoring planner resources at {}:{}".format(host, port))
    print("Press C-c to stop...")
    while True:
        print_planner_resources(host, port)
        sleep(5)
