from tasks.util.env import PROJ_ROOT
from subprocess import run, PIPE
import json


def get_hoststats_proxy_ip(namespace):
    res = run(
        "kubectl -n {} get service hoststats-proxy -o json".format(namespace),
        stdout=PIPE,
        stderr=PIPE,
        cwd=PROJ_ROOT,
        shell=True,
        check=True,
    )

    data = json.loads(res.stdout.decode("utf-8"))
    ip = data["spec"]["clusterIP"]
    print("Got hoststats proxy IP {}".format(ip))
    return ip
