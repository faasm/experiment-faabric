from invoke import task
import requests
from subprocess import check_output
import time

UPLOAD_PORT = 8002
INVOKE_PORT = 80


def do_post(url, input, headers=None, quiet=False, json=False, debug=False):
    if debug:
        print("POST URL    : {}".format(url))
        print("POST Headers: {}".format(headers))
        print("POST JSON   : {}".format(json))
        print("POST Data   : {}".format(input))

    if json:
        response = requests.post(url, json=input, headers=headers)
    else:
        response = requests.post(url, data=input, headers=headers)

    if response.status_code >= 400:
        print("Request failed: status = {}".format(response.status_code))
    elif response.text and not quiet:
        print(response.text)
    elif not quiet:
        print("Empty response")

    return response.text


def get_k8s_service_ip(namespace, service_name):
    cmd = "kubectl get -n {} service {} -o 'jsonpath={{.status.loadBalancer.ingress[0].ip}}'".format(
        namespace, service_name
    )
    return check_output(cmd, shell=True).decode("utf-8")


def curl_file(url, file_path, headers=None, quiet=False):
    cmd = ["curl", "-X", "PUT", url, "-T", file_path]

    headers = headers if headers else {}
    for key, value in headers.items():
        cmd.append('-H "{}: {}"'.format(key, value))

    cmd = " ".join(cmd)

    if not quiet:
        print(cmd)

    res = subprocess.call(cmd, shell=True)

    if res == 0 and not quiet:
        print("Successfully PUT file {} to {}".format(file_path, url))
    elif res != 0:
        raise RuntimeError("Failed PUTting file {} to {}".format(file_path, url))


def get_faasm_upload_host_port():
    host = get_k8s_service_ip("faasm", "upload")
    port = UPLOAD_PORT
    return host, port


def get_faasm_invoke_host_port():
    host = get_k8s_service_ip("istio-system", "istio-ingressgateway")
    port = INVOKE_PORT
    return host, port


def get_knative_headers(service_name):
    cmd = "kn service describe faasm-{} -o url -n faasm".format(service_name)
    url = check_output(cmd, shell=True).decode("utf-8").strip()[7:]
    return {"Host": "{}".format(url)}


def invoke_impl(user, func, cmdline="", mpi_np=1, debug=False):
    """
    Invoke a function execution in the faasm runtime with knative
    """
    host, port = get_faasm_invoke_host_port()
    url = "http://{}".format(host)

    headers = get_knative_headers("worker")

    msg = {
        "user": user,
        "function": func,
        "mpi_world_size": mpi_np,
        "cmdline": cmdline,
        "async": False,
    }

    return do_post(url, msg, headers=headers, json=True, debug=debug)


def upload_impl(user, func):
    func_file = join(WASM_DIR, user, func, "function.wasm")
    url = "http://{}:{}/f/{}/{}".format(host, port, user, func)
    curl_file(url, func_file)
