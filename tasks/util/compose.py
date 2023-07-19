from subprocess import run


def run_compose_cmd(thread_id, compose_dir, compose_cmd):
    # Note that we actually run a docker command as we specify the container
    # by name
    docker_cmd = "docker {}".format(compose_cmd)
    print("[Thread {}] {}".format(thread_id, docker_cmd))
    run(
        docker_cmd,
        shell=True,
        check=True,
        cwd=compose_dir,
        capture_output=True,
    )
