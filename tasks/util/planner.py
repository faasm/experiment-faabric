from faasmctl.util.planner import (
    get_available_hosts as planner_get_available_hosts,
    get_in_fligh_apps as planner_get_in_fligh_apps,
)
from time import sleep


# This method also returns the number of used VMs
def get_num_idle_cpus_from_in_flight_apps(
    num_vms, num_cpus_per_vm, in_flight_apps
):
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


def get_num_available_slots_from_in_flight_apps(
    num_vms,
    num_cpus_per_vm,
    user_id=None,
    num_evicted_vms=None,
    openmp=False,
):
    """
    For Granny baselines, we cannot use static knowledge of the
    allocated slots, as migrations may happen so we query the planner
    """
    short_sleep_secs = 0.25
    long_sleep_secs = 1

    while True:
        in_flight_apps = planner_get_in_fligh_apps()
        available_hosts = planner_get_available_hosts()
        available_ips = [host.ip for host in available_hosts.hosts]

        if len(available_ips) != num_vms:
            print(
                "Not enough hosts registered ({}/{}). Retrying...".format(
                    len(available_ips), num_vms
                )
            )
            sleep(short_sleep_secs)
            continue

        available_slots = sum(
            [
                int(host.slots - host.usedSlots)
                for host in available_hosts.hosts
            ]
        )

        next_evicted_vm_ips = []
        try:
            next_evicted_vm_ips = in_flight_apps.nextEvictedVmIps
        except AttributeError:
            pass

        if (
            num_evicted_vms is not None
            and len(next_evicted_vm_ips) != num_evicted_vms
        ):
            print("Not enough evicted VMs registered. Retrying...")
            sleep(short_sleep_secs)
            continue

        worker_occupation = {}

        for next_evicted_vm_ip in next_evicted_vm_ips:
            worker_occupation[next_evicted_vm_ip] = int(num_cpus_per_vm)
            available_slots -= int(num_cpus_per_vm)

        # Annoyingly, we may query for the in-flight apps as soon as we
        # schedule them, missing the init stage of the mpi app. Thus we
        # sleep for a bit and ask again (we allow the size to go over the
        # specified size in case of an elsatic scale-up)
        if any([len(app.hostIps) < app.size for app in in_flight_apps.apps]):
            print("App not fully in-flight. We wait...")
            sleep(short_sleep_secs)
            continue

        # Also prevent from scheduling an app while another app is waiting
        # to be migrated from an evicted VM
        must_hold_back = False
        for app in in_flight_apps.apps:
            if any([ip in next_evicted_vm_ips for ip in app.hostIps]):
                print(
                    "Detected app {} scheduled in to-be evicted VM. Retrying...".format(
                        app.appId
                    )
                )
                must_hold_back = True
                break

        if must_hold_back:
            sleep(long_sleep_secs)
            continue

        for app in in_flight_apps.apps:
            # If the subtype is 0, protobuf will optimise it away and the field
            # won't be there. This try/except guards against that
            this_app_uid = 0
            try:
                this_app_uid = app.subType
            except AttributeError:
                pass

            must_prune_vm = user_id is not None and user_id != this_app_uid

            for ip in app.hostIps:

                # This pruning corresponds to a multi-tenant setting using
                # mpi-evict
                if must_prune_vm:
                    worker_occupation[ip] = int(num_cpus_per_vm)
                    continue

                if ip not in worker_occupation:
                    worker_occupation[ip] = 0

                if worker_occupation[ip] < int(num_cpus_per_vm):
                    worker_occupation[ip] += 1

        # For OpenMP, we only care if any VM has enough slots to run the full
        # application. Otherwise we wait.
        if openmp:
            if num_vms > len(list(worker_occupation.keys())):
                return num_cpus_per_vm

            return max(
                [
                    num_cpus_per_vm - worker_occupation[ip]
                    for ip in worker_occupation
                ]
            )

        num_available_slots = (
            num_vms - len(list(worker_occupation.keys()))
        ) * num_cpus_per_vm
        for ip in worker_occupation:
            num_available_slots += num_cpus_per_vm - worker_occupation[ip]

        # Double-check the number of available slots with our other source of truth
        if user_id is not None and num_available_slots != available_slots:
            print(
                "WARNING: inconsistency in the number of available slots"
                " (in flight: {} - registered: {})".format(
                    num_available_slots, available_slots
                )
            )
            sleep(short_sleep_secs)
            continue

        # If we have made it this far, we are done
        break

    # If we have any frozen apps, we want to un-FREEZE them to prevent building
    # up a buffer in the planner
    if len(in_flight_apps.frozenApps) > 0:
        print(
            "Detected frozen apps, so returning 0 slots: {}".format(
                in_flight_apps.frozenApps
            )
        )
        return 0

    return num_available_slots


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
        count += sum(part[0:ind] + part[ind + 1 :]) * part[ind]

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
