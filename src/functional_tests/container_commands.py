import os
import subprocess

USER = "elspeth"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]"}


def reset_database(host):
    if host not in LOCAL_HOSTS:
        allowed_host = os.environ.get("ALLOW_REMOTE_DB_RESET")
        if allowed_host != host:
            raise RuntimeError(
                "Remote database reset refused. Set ALLOW_REMOTE_DB_RESET "
                f"to the exact test host ({host!r}) to confirm."
            )

    return _exec_in_container(
        host,
        ["/usr/local/bin/python", "/src/manage.py", "reset_test_database"],
    )


def approve_user(host, username):
    if host not in LOCAL_HOSTS:
        allowed_host = os.environ.get("ALLOW_REMOTE_DB_RESET")
        if allowed_host != host:
            raise RuntimeError(
                "Remote user approval refused. Set ALLOW_REMOTE_DB_RESET "
                f"to the exact test host ({host!r}) to confirm."
            )

    return _exec_in_container(
        host,
        ["/usr/local/bin/python", "/src/manage.py", "approve_test_user", username],
    )


def _exec_in_container(host, commands):
    if host in LOCAL_HOSTS:
        return _exec_in_container_locally(commands)
    else:
        return _exec_in_container_on_server(host, commands)


def _exec_in_container_locally(commands):
    print(f"Running {commands} on inside local docker container")
    return _run_commands(["docker", "exec", _get_container_id()] + commands)


def _exec_in_container_on_server(host, commands):
    print(f"Running {commands!r} on {host} inside docker container")
    return _run_commands(
        ["ssh", f"{USER}@{host}", "docker", "exec", "superlists"] + commands
    )


def _get_container_id():
    return subprocess.check_output(
        ["docker", "ps", "-q", "--filter", "ancestor=superlists"]
    ).strip()


def _run_commands(commands):
    process = subprocess.run(
        commands,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    result = process.stdout.decode()
    if process.returncode != 0:
        raise Exception(result)
    print(f"Result: {result!r}")
    return result.strip()
