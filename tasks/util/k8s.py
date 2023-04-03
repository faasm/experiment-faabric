from subprocess import run
from time import sleep


def wait_for_pods(namespace, label):
    # Wait for the faasm pods to be ready
    while True:
        print("Waiting for {} pods...".format(namespace))
        cmd = [
            "kubectl",
            "-n {}".format(namespace),
            "get pods -l {}".format(label),
            "-o jsonpath='{..status.conditions[?(@.type==\"Ready\")].status}'",
        ]
        cmd = " ".join(cmd)

        output = run(cmd, shell=True, check=True, capture_output=True).stdout.decode("utf-8").rstrip()
        statuses = [o.strip() for o in output.split(" ") if o.strip()]
        if all([s == "True" for s in statuses]):
            print("All {} pods ready, continuing...".format(namespace))
            break

        print("{} pods not ready, waiting ({})".format(namespace, output))
        sleep(5)
