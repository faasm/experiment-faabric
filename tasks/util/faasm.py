from configparser import ConfigParser
from os.path import expanduser, join, exists

FAASM_INI_FILE = join(expanduser("~"), ".config", "faasm.ini")


def get_faasm_ini_value(section, key):
    if not exists(FAASM_INI_FILE):
        print("Expected to find faasm config at {}".format(FAASM_INI_FILE))
        raise RuntimeError("Did not find faasm config")

    config = ConfigParser()
    config.read(FAASM_INI_FILE)
    return config[section].get(key, "")


def get_faasm_upload_host_port():
    host = get_faasm_ini_value("Faasm", "upload_host")
    port = get_faasm_ini_value("Faasm", "upload_port")

    print("Using faasm upload {}:{}".format(host, port))
    return host, port


def get_faasm_invoke_host_port():
    host = get_faasm_ini_value("Faasm", "invoke_host")
    port = get_faasm_ini_value("Faasm", "invoke_port")

    print("Using faasm invoke {}:{}".format(host, port))
    return host, port


def get_faasm_hoststats_proxy_host_port():
    host = get_faasm_ini_value("Faasm", "hoststats_host")
    port = get_faasm_ini_value("Faasm", "hoststats_port")
    print("Using faasm hoststats {}:{}".format(host, port))
    return host, port


def get_faasm_worker_pods():
    pods = get_faasm_ini_value("Faasm", "worker_names")
    pods = [p.strip() for p in pods.split(",") if p.strip()]

    print("Using faasm worker pods: {}".format(pods))
    return pods


def get_knative_headers():
    knative_host = get_faasm_ini_value("Faasm", "knative_host")

    headers = {"Host": knative_host}
    print("Using faasm knative headers: {}".format(headers))

    return headers
