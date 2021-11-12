import json
import matplotlib.pyplot as plt
import networkx as nx

from math import sqrt

HOST_COLOURS = [
    "red",
    "blue",
    "green",
    "yellow",
    "orange",
    "plum1",
]
MPI_GRAPH_PATH = "/tmp/faasm_mpi_graph.png"
MPI_XMSG_PATH = "/tmp/faasm_mpi_xmsg.png"
MIN_EDGE_WEIGHT = 10
MPI_MSGCOUNT_PREFIX = "mpi-msgcount-torank-"
MPI_MSGTYPE_PREFIX = "mpi-msgtype-torank-"  # mpi-msgtype-torank-0-6:31234
MPI_MSG_TYPE_MAP = {
    0: "NORMAL",
    1: "BARRIER_JOIN",
    2: "BARRIER_DONE",
    3: "SCATTER",
    4: "GATHER",
    5: "ALLGATHER",
    6: "REDUCE",
    7: "SCAN",
    8: "ALLREDUCE",
    9: "ALLTOALL",
    10: "SENDRECV",
}


def get_hosts_from_node(node):
    node_hosts = set()
    node_host = node["msg"].get("exec_host", "")
    node_hosts.add(node_host)

    children = node.get("chained", list())
    for c in children:
        child_hosts = get_hosts_from_node(c)
        node_hosts = node_hosts.union(child_hosts)

    return node_hosts


def get_hosts_colour_map(root_node):
    all_hosts = get_hosts_from_node(root_node)

    cmp = dict()
    for i, h in enumerate(all_hosts):
        cmp[h] = HOST_COLOURS[i % len(HOST_COLOURS)]

    return cmp


def get_mpi_messages_from_msg(msg):
    all_msg = msg.get("int_exec_graph_detail", "").split(",")
    all_mpi_msg = [
        m for m in all_msg if MPI_MSGCOUNT_PREFIX in m.split(":")[0]
    ]
    recv_ranks = [int(m.split(":")[0].split("-")[-1]) for m in all_mpi_msg]
    num_msg = [int(m.split(":")[1]) for m in all_mpi_msg]

    ret_list = []
    my_rank = msg.get("mpi_rank", 0)
    for rank, count in zip(recv_ranks, num_msg):
        ret_list.append([(my_rank, rank), count])
    return ret_list


def get_mpi_message_breakdown_from_msg(msg):
    all_msg = msg.get("int_exec_graph_detail", "").split(",")
    all_mpi_msg = [m for m in all_msg if MPI_MSGTYPE_PREFIX in m.split(":")[0]]
    msg_type = [int(m.split(":")[0].split("-")[-2]) for m in all_mpi_msg]
    recv_ranks = [int(m.split(":")[0].split("-")[-1]) for m in all_mpi_msg]
    num_msg = [int(m.split(":")[1]) for m in all_mpi_msg]

    ret_dict = {}
    my_rank = msg.get("mpi_rank", 0)
    for m_type, rank, count in zip(msg_type, recv_ranks, num_msg):
        if m_type not in ret_dict:
            ret_dict[m_type] = []
        ret_dict[m_type].append([(my_rank, rank), count])

    return ret_dict


def get_mpi_details_from_node(node):
    mpi_nodes = {}
    node_rank = node["msg"].get("mpi_rank", 0)
    node_host = node["msg"].get("exec_host", "")
    node_world_size = node["msg"].get("mpi_world_size", "")
    mpi_msg_count = get_mpi_messages_from_msg(node["msg"])
    mpi_msg_type_bdwon = get_mpi_message_breakdown_from_msg(node["msg"])
    mpi_nodes[node_rank] = {
        "host": node_host,
        "world_size": node_world_size,
        "msg_count": mpi_msg_count,
        "msg_type_breakdown": mpi_msg_type_bdwon,
    }

    children = node.get("chained", list())
    for c in children:
        child_details = get_mpi_details_from_node(c)
        mpi_nodes = {**mpi_nodes, **child_details}

    return mpi_nodes


def get_grid_size(world_size):
    def is_perfect_square(num):
        return int(sqrt(num) + 0.5) ** 2 == num

    def largest_power_of_two(num):
        if num % 2 != 0:
            return 1
        factor = 0
        while num % 2 == 0 and num > 2:
            num /= 2
            factor += 1
        return 2 ** factor

    if is_perfect_square(world_size):
        return [int(sqrt(world_size)), int(sqrt(world_size))]

    power_two = largest_power_of_two(world_size)
    fraction = int(world_size / power_two)

    if power_two > fraction:
        return [power_two, fraction]

    return [fraction, power_two]


def get_node_pos(world_size, with_offset=False):
    pos = {}
    nrows, ncols = get_grid_size(world_size)

    for i in range(world_size):
        if with_offset:
            x_offset = 0.5 * ((i / ncols) % 2)
            if ncols > 2:
                y_offset = 0.25 * ((i % ncols) % 2)
            else:
                y_offset = 0
        else:
            x_offset = 0
            y_offset = 0
        pos[i] = [x_offset + i % ncols, y_offset - int(i / ncols)]

    return pos


def are_neighbors(world_size, a, b):
    pos = get_node_pos(world_size, False)

    directions = [[0, 1], [0, -1], [1, 0], [-1, 0]]
    for d in directions:
        if [sum(x) for x in zip(pos[a], d)] == pos[b]:
            return True

    return False


def are_periodic_neighbors(world_size, a, b):
    nrows, ncols = get_grid_size(world_size)
    pos = get_node_pos(world_size, False)

    if (ncols > 2) and (pos[a][0] * pos[b][0] == 0):
        if (pos[a][1] == pos[b][1]) and (pos[a][0] + pos[b][0] == (ncols - 1)):
            return True

    if (nrows > 2) and (pos[a][1] * pos[b][1] == 0):
        if (pos[a][0] == pos[b][0]) and (
            pos[a][1] + pos[b][1] == -(nrows - 1)
        ):
            return True

    return False


def apply_zero_correction(nodes):
    """
    Subtract from each ingress/egress edge to/from the master node (rank 0) the
    minimum inbound/outbound weight. We assume this baseline to be due to
    synchronisation comms.
    """

    def find_min_weight_to_from_zero(nodes):
        w_to = 1e8
        w_from = 1e8
        for key in nodes:
            for e in nodes[key]["msg_count"]:
                if e[0][0] == 0 and e[1] < w_from:
                    w_from = e[1]
                if e[0][1] == 0 and e[1] < w_to:
                    w_to = e[1]
        return w_to, w_from

    # Find minimum weights ingressing and egressing from zero
    w_to, w_from = find_min_weight_to_from_zero(nodes)
    # Subtract minimum weights from all edges
    for key in nodes:
        for e in nodes[key]["msg_count"]:
            if e[0][0] == 0:
                e[1] -= w_from
            if e[0][1] == 0:
                e[1] -= w_to


def add_periodic_edge(graph, pos, world_size, key, e):
    nrows, ncols = get_grid_size(world_size)
    pos = get_node_pos(world_size, False)

    x = pos[e[0][0]][0]
    y = pos[e[0][0]][1]

    to_x = pos[e[0][1]][0]
    to_y = pos[e[0][1]][1]

    vertical = x == to_x
    horizontal = y == to_y

    if key == 0:
        new_key = -99
    else:
        new_key = -key

    if vertical:
        new_key -= 100

    ret = {}
    offset = 0.75
    if x == 0 and horizontal:
        graph.add_node(new_key)
        graph.add_edge(key, new_key, weight=e[1])
        ret.update({new_key: [x - offset, y]})
    if x == ncols - 1 and horizontal:
        graph.add_node(new_key)
        graph.add_edge(key, new_key, weight=e[1])
        ret.update({new_key: [x + offset, y]})
    if y == 0 and vertical:
        graph.add_node(new_key)
        graph.add_edge(key, new_key, weight=e[1])
        ret.update({new_key: [x, y + offset]})
    if y == -(nrows - 1) and vertical:
        graph.add_node(new_key)
        graph.add_edge(key, new_key, weight=e[1])
        ret.update({new_key: [x, y - offset]})

    return ret


def plot_graph(
    nodes,
    pos,
    cmp,
    min_weight=MIN_EDGE_WEIGHT,
    zero_correction=True,
    msg_type=-1,
):
    graph = nx.DiGraph()
    graph_cmp = []
    world_size = len(nodes.keys())

    # ----- Add edges to graph ----- #

    if zero_correction:
        apply_zero_correction(nodes)
    for key in nodes:
        graph.add_node(key, host=nodes[key]["host"], rank=key % 2)
        graph_cmp.append(cmp[nodes[key]["host"]])

        # Choose the edge list to iterate on depending on the message type to
        # plot
        node_list = nodes[key]["msg_count"]
        if msg_type != -1:
            if msg_type in nodes[key]["msg_type_breakdown"]:
                node_list = nodes[key]["msg_type_breakdown"][msg_type]
            else:
                node_list = []

        for e in node_list:
            if e[1] > MIN_EDGE_WEIGHT:
                if not are_neighbors(world_size, e[0][0], e[0][1]):
                    if not are_periodic_neighbors(
                        world_size, e[0][0], e[0][1]
                    ):
                        print(
                            "Adding an edge between two non-neighbours! {}->{}".format(
                                e[0][0], e[0][1]
                            )
                        )
                    else:
                        print("Adding periodic edge: {} - {}".format(key, e))
                        new_pos = add_periodic_edge(
                            graph, pos, world_size, key, e
                        )
                        pos.update(new_pos)
                        continue
                graph.add_edge(e[0][0], e[0][1], weight=e[1])

    # ----- Plot graph -----

    plt.figure(figsize=(20, 20))
    ax = plt.axes()
    plt.gca().set_aspect("equal", adjustable="box")

    # nx.draw(graph, pos, with_labels=True, node_color=graph_cmp)
    real_nodes = [i for i in sorted(list(graph)) if i >= 0]
    periodic_nodes = [i for i in sorted(list(graph)) if i < 0]
    nx.draw_networkx_nodes(
        graph,
        pos,
        ax=ax,
        nodelist=real_nodes,
        node_color=graph_cmp,
    )
    nx.draw_networkx_nodes(
        graph,
        pos,
        ax=ax,
        nodelist=periodic_nodes,
        node_color="white",
    )
    nx.draw_networkx_labels(
        graph, pos, labels={n: n for n in graph if n >= 0}, ax=ax
    )
    nx.draw_networkx_edges(graph, pos, ax=ax)
    labels = nx.get_edge_attributes(graph, "weight")
    nx.draw_networkx_edge_labels(
        graph, pos, edge_labels=labels, ax=ax, label_pos=0.75, font_size=14
    )

    # Set title
    title_str = "MPI Message Graph"
    if msg_type != -1:
        title_str += " (msg type: {})".format(MPI_MSG_TYPE_MAP[msg_type])
    plt.title(title_str, fontdict={"fontsize": 18, "fontweight": "bold"})

    # Save figure
    plt.savefig(MPI_GRAPH_PATH)


def plot_mpi_graph(json_str, msg_type=-1):
    """
    Plot the MPI message graph given the execution graph as a json string, and
    the message type we want to plot.
    """
    json_obj = json.loads(json_str)

    root_node = json_obj["root"]
    cmp = get_hosts_colour_map(root_node)

    world_size = root_node["msg"].get("mpi_world_size")
    pos = get_node_pos(world_size)

    mpi_nodes = get_mpi_details_from_node(root_node)

    if msg_type == -1:
        print(
            "Plotting all message graph with corrections and min edge weight"
        )
        plot_graph(mpi_nodes, pos, cmp)
    else:
        print(
            "Plotting message graph for message type: {}".format(
                MPI_MSG_TYPE_MAP[msg_type]
            )
        )
        plot_graph(
            mpi_nodes,
            pos,
            cmp,
            min_weight=0,
            zero_correction=False,
            msg_type=msg_type,
        )

    print("Saved graph in file: {}".format(MPI_GRAPH_PATH))


def is_cross_host(mpi_nodes, edge):

    out_node_key = edge[0][0]
    in_node_key = edge[0][1]
    return mpi_nodes[out_node_key]["host"] != mpi_nodes[in_node_key]["host"]


def plot_mpi_cross_host_msg(json_str):
    """
    Plot the breakdown of cross-host messaging by message type
    """
    json_obj = json.loads(json_str)
    root_node = json_obj["root"]
    world_size = root_node["msg"].get("mpi_world_size")
    mpi_nodes = get_mpi_details_from_node(root_node)

    # ----- Plot bar chart -----

    fig, ax = plt.subplots()

    labels = MPI_MSG_TYPE_MAP.keys()
    prev_values = [0 for _ in labels]

    for node_rank in mpi_nodes:
        values = [0 for _ in labels]
        for m_type in mpi_nodes[node_rank]["msg_type_breakdown"]:
            edge_list = mpi_nodes[node_rank]["msg_type_breakdown"][m_type]
            values[m_type] += sum(
                [e[1] for e in edge_list if is_cross_host(mpi_nodes, e)]
            )

        ax.bar(
            labels,
            values,
            bottom=prev_values,
            label="Rank: {}".format(node_rank),
        )
        prev_values = [sum(x) for x in zip(values, prev_values)]

    ax.legend()

    # Set labels
    ax.set_xticks(list(MPI_MSG_TYPE_MAP.keys()))
    ax.set_xticklabels(
        list(MPI_MSG_TYPE_MAP.values()), fontdict={"fontsize": 7}
    )
    plt.setp(
        ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor"
    )

    plt.title(
        "Breakdown of cross-host messages per message type and rank\n"
        "World size: {}".format(world_size)
    )
    plt.savefig(MPI_XMSG_PATH)

    print("Saved graph in file: {}".format(MPI_XMSG_PATH))
