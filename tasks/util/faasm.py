from subprocess import run, PIPE


def get_faasm_worker_pods():
    kubecmd = [
        "kubectl",
        "-n faasm",
        "get pods",
        "-l serving.knative.dev/service=faasm-worker",
        "-o wide",
    ]

    kubecmd = " ".join(kubecmd)
    print(kubecmd)
    res = run(
        kubecmd,
        stdout=PIPE,
        stderr=PIPE,
        shell=True,
        check=True,
    )

    cmd_out = res.stdout.decode("utf-8")

    # Split output into list of strings
    lines = cmd_out.split("\n")[1:]
    lines = [l.strip() for l in lines if l.strip()]

    pod_names = list()
    pod_ips = list()
    for line in lines:
        line_parts = line.split(" ")
        line_parts = [p.strip() for p in line_parts if p.strip()]

        pod_names.append(line_parts[0])
        pod_ips.append(line_parts[5])

    return pod_names, pod_ips
