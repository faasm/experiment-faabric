from subprocess import run, PIPE
from os.path import join
from os import makedirs
from jinja2 import Environment, FileSystemLoader

from tasks.util.env import (
    PROJ_ROOT,
    get_docker_tag,
)

NATIVE_HOSTFILE = "/home/mpirun/hostfile"

HOSTFILE_LOCAL_FILE = "/tmp/hostfile"
# NOTE: the slots per host must be the same as the number of vCPUs
# in the VMs in the k8s deployment. The VM type is defined at:
# https://github.com/faasm/experiment-base/blob/54501493187fa7a162b9aa27e67c5ef5e9389348/tasks/util/env.py#L16
SLOTS_PER_HOST = 4


def get_native_mpi_namespace(experiment_name):
    return "openmpi-{}".format(experiment_name)


def _template_k8s_file(experiment_name, filename, template_vars):
    # Prepare output file
    output_dir = join(PROJ_ROOT, "k8s", "templated")
    makedirs(output_dir, exist_ok=True)
    output_file = join(
        output_dir,
        "{}-{}.yml".format(filename, experiment_name),
    )

    # Load template
    k8s_dir = join(PROJ_ROOT, "k8s")
    template_file = "{}.yml.j2".format(filename)

    # Render the template
    env = Environment(
        loader=FileSystemLoader(k8s_dir), trim_blocks=True, lstrip_blocks=True
    )
    template = env.get_template(template_file)
    output_data = template.render(template_vars)

    # Write to the output file
    with open(output_file, "w") as fh:
        fh.write(output_data)

    return output_file


def _template_k8s_files(experiment_name, image_name, num_nodes=4):
    image_tag = get_docker_tag(image_name)
    namespace = get_native_mpi_namespace(experiment_name)
    template_vars = {
        "native_mpi_namespace": namespace,
        "native_mpi_image": image_tag,
        "num_nodes": num_nodes,
    }

    namespace_yml = _template_k8s_file(
        experiment_name, "namespace", template_vars
    )
    deployment_yml = _template_k8s_file(
        experiment_name, "deployment", template_vars
    )

    return namespace_yml, deployment_yml


def run_kubectl_cmd(experiment_name, cmd):
    namespace = get_native_mpi_namespace(experiment_name)
    kubecmd = "kubectl -n {} {}".format(namespace, cmd)
    print(kubecmd)
    res = run(
        kubecmd,
        stdout=PIPE,
        stderr=PIPE,
        cwd=PROJ_ROOT,
        shell=True,
        check=True,
    )

    return res.stdout.decode("utf-8")


def get_native_mpi_pods(experiment_name):
    # List all pods
    cmd_out = run_kubectl_cmd(
        experiment_name, "get pods -o wide -l run=faasm-openmpi"
    )
    print(cmd_out)

    # Split output into list of strings
    lines = cmd_out.split("\n")[1:]
    lines = [line.strip() for line in lines if line.strip()]

    pod_names = list()
    pod_ips = list()
    for line in lines:
        line_parts = line.split(" ")
        line_parts = [p.strip() for p in line_parts if p.strip()]

        pod_names.append(line_parts[0])
        pod_ips.append(line_parts[5])

    print("Got pods: {}".format(pod_names))
    print("Got IPs: {}".format(pod_ips))

    return pod_names, pod_ips


def deploy_native_mpi(experiment_name, image_name, num_nodes):
    namespace_yml, deployment_yml = _template_k8s_files(
        experiment_name, image_name, num_nodes
    )
    run(
        "kubectl apply -f {}".format(namespace_yml),
        shell=True,
        check=True,
    )

    run(
        "kubectl apply -f {}".format(deployment_yml),
        shell=True,
        check=True,
    )


def delete_native_mpi(experiment_name, image_name, num_nodes):
    _, deployment_yml = _template_k8s_files(
        experiment_name, image_name, num_nodes
    )

    # Note we don't delete the namespace as it takes a while and doesn't do any
    # harm to leave it
    run(
        "kubectl delete -f {}".format(deployment_yml),
        shell=True,
        check=True,
    )


def generate_native_mpi_hostfile(experiment_name, slots=SLOTS_PER_HOST):
    pod_names, pod_ips = get_native_mpi_pods(experiment_name)

    with open(HOSTFILE_LOCAL_FILE, "w") as fh:
        for ip in pod_ips:
            fh.write("{} slots={}\n".format(ip, slots))

    # SCP the hostfile to all hosts
    for pod_name in pod_names:
        run_kubectl_cmd(
            experiment_name,
            "cp {} {}:{}".format(
                HOSTFILE_LOCAL_FILE, pod_name, NATIVE_HOSTFILE
            ),
        )
