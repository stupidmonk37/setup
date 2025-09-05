import argparse
import json
import subprocess
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from utils import (
    display_rack_table,
    display_crossrack_table,
    valid_rack_name,
    valid_crossrack_name,
    display_node_table,
    get_data_cluster,
    display_cluster_table,
    print_cluster_summary,
    print_failed_validations,
    handle_faults,
    fetch_faults,
    display_faults,
    expand_crossrack_names,
)


# Subcommand handlers
def handle_cluster(args):
    data = get_data_cluster()
    #display_cluster_table(data, args.racks)
    display_cluster_table(data["racks"], args.racks)
    print_cluster_summary(None, data["summary"])
    #print_failed_validations()
    # show all faults for cluster
    faults = fetch_faults()
    display_faults(faults)


def handle_node(args):
    display_node_table(args.racks, render=True)
    faults = fetch_faults()
    display_faults(faults, racks=args.racks)


def handle_rack(args):
    display_rack_table(args.racks)
    faults = fetch_faults()
    display_faults(faults, racks=args.racks)


def handle_crossrack(args):
    display_crossrack_table(args.racks)
    faults = fetch_faults()
    expanded_racks = expand_crossrack_names(args.racks)
    display_faults(faults, racks=expanded_racks)


def handle_faults(args):
    faults = fetch_faults()
    if args.racks:
        display_faults(faults, racks=args.racks)
    else:
        display_faults(faults)



# Main
def main():
    parser = argparse.ArgumentParser(description="Groq Validationd Dashboard CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Cluster
    cluster_parser = subparsers.add_parser("cluster")
    cluster_parser.add_argument("--racks", nargs="+", type=valid_rack_name)
    cluster_parser.set_defaults(func=handle_cluster)

    # Node
    node_parser = subparsers.add_parser("node")
    node_parser.add_argument("--racks", nargs="+", type=valid_rack_name, required=True)
    node_parser.set_defaults(func=handle_node)

    # Rack
    rack_parser = subparsers.add_parser("rack")
    rack_parser.add_argument("--racks", nargs="+", type=valid_rack_name, required=True)
    rack_parser.set_defaults(func=handle_rack)

    # Crossrack
    cross_parser = subparsers.add_parser("crossrack")
    cross_parser.add_argument("--racks", nargs="+", type=valid_crossrack_name, required=True)
    cross_parser.set_defaults(func=handle_crossrack)

    # Faults
    faults_parser = subparsers.add_parser("faults")
    faults_parser.add_argument("--racks", nargs="+", type=valid_rack_name, help="Filter faults by rack(s)")
    faults_parser.set_defaults(func=handle_faults)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
