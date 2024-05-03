from subprocess import run
from time import sleep


def wait_for_pods(namespace, label, num_expected=1, quiet=False):
    # Wait for the faasm pods to be ready
    while True:
        if not quiet:
            print("Waiting for {} pods...".format(namespace))
        cmd = [
            "kubectl",
            "-n {}".format(namespace),
            "get pods -l {}".format(label),
            "-o jsonpath='{..status.conditions[?(@.type==\"Ready\")].status}'",
        ]
        cmd = " ".join(cmd)

        output = (
            run(cmd, shell=True, check=True, capture_output=True)
            .stdout.decode("utf-8")
            .rstrip()
        )
        statuses = [o.strip() for o in output.split(" ") if o.strip()]
        statuses = [s == "True" for s in statuses]
        true_statuses = [s for s in statuses if s]
        if len(true_statuses) == num_expected and all(statuses):
            if not quiet:
                print("All {} pods ready, continuing...".format(namespace))
            break

        if not quiet:
            print("{} pods not ready, waiting ({}/{})".format(namespace, len(true_statuses), num_expected))
        sleep(5)
