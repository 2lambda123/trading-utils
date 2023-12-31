import logging
import subprocess


def run_cmd(cmd, in_shell=True):
    logging.info(f"Running command: {cmd}")
    subprocess.call(cmd, shell=in_shell)


def open_file(file_path):
    run_cmd("open {}".format(file_path))


def open_in_browser(target_file):
    run_cmd("open {}".format(target_file))
