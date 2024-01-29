from faasmctl.util.planner import get_available_hosts


def generate_host_list(num_on_each_host):
    """
    Generate a host list given an array of the number of MPI processes that
    need to go in each host.
    """
    avail_hosts = get_available_hosts()
    host_list = []

    # Sanity check the host list. First, for this experiment we should only
    # have two regsitered workers
    assert (
        len(avail_hosts.hosts) >= len(num_on_each_host)
    ), "Not enough available hosts (have: {} - need: {})".format(len(avail_hosts.hosts), num_on_each_host)
    for ind, num_in_host in enumerate(num_on_each_host):
        host = avail_hosts.hosts[ind]
        # Second, each host should have no other running messages
        # assert host.usedSlots == 0, "Not enough free slots on host!"
        # Third, each host should have enough slots to run the requested number
        # of messages
        assert host.slots >= num_in_host, "Not enough slots on host!"

        host_list = host_list + int(num_in_host) * [host.ip]

    return host_list


