import requests
from subprocess import check_output


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
