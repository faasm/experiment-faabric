# This method also returns the number of used VMs
def get_num_idle_cpus_from_in_flight_apps(num_vms, num_cpus_per_vm, in_flight_apps):
    total_cpus = int(num_vms) * int(num_cpus_per_vm)

    worker_occupation = {}
    total_used_cpus = 0
    for app in in_flight_apps.apps:
        for ip in app.hostIps:
            if ip not in worker_occupation:
                worker_occupation[ip] = 0

            worker_occupation[ip] += 1
            total_used_cpus += 1

    num_idle_vms = int(num_vms) - len(worker_occupation.keys())
    num_idle_cpus = total_cpus - total_used_cpus

    return num_idle_vms, num_idle_cpus


def get_xvm_links_from_part(part):
    """
    Calculate the number of cross-VM links for a given partition

    The number of cross-VM links is the sum for each process of all the
    non-local processes divided by two.
    """
    if len(part) == 1:
        return 0

    count = 0
    for ind in range(len(part)):
        count += sum(part[0:ind] + part[ind + 1:]) * part[ind]

    return int(count / 2)


def get_num_xvm_links_from_in_flight_apps(in_flight_apps):
    total_xvm_links = 0

    for app in in_flight_apps.apps:
        app_ocupation = {}
        for ip in app.hostIps:
            if ip not in app_ocupation:
                app_ocupation[ip] = 0
            app_ocupation[ip] += 1

        part = list(app_ocupation.values())
        # TODO: delete me
#    print("DEBUG - App: {} - Occupation: {} - Part: {} - Links: {}".format(
#               app.appId,
#               app_ocupation,
#               part,
#               get_xvm_links_from_part(part)))
        total_xvm_links += get_xvm_links_from_part(part)

    return total_xvm_links
