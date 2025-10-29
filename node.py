"""
node.py
Lamport Distributed Mutual Exclusion simulation using xmlrpc (SimpleRPC).
Run this file 3 times (or N times) with different --id values and ports.

Usage example:
    python node.py --id 1 --config nodes_config.json
    python node.py --id 2 --config nodes_config.json
    python node.py --id 3 --config nodes_config.json
"""

import argparse
import json
import threading
import time
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.client import ServerProxy
import sys
import os
from datetime import datetime
import socket
import random

class LamportNode:
    def __init__(self, node_id, url, peers):
        self.node_id = str(node_id)
        self.url = url
        self.peers = {str(k): v for k, v in peers.items() if str(k) != str(node_id)}

        # Lamport clock
        self.clock = 0
        self.clock_lock = threading.Lock()

        # Request queue
        self.queue_lock = threading.Lock()
        self.request_queue = []

        self.requesting = False
        self.own_request_ts = None

        # Replies and deferred replies
        self.replies_lock = threading.Lock()
        self.replies_received = set()

        self.deferred_lock = threading.Lock()
        self.deferred = set()

        # Logging
        self.logfile = f"log_node{self.node_id}.txt"
        self.ledger_file = "shared_ledger.txt"
        if not os.path.exists(self.ledger_file):
            open(self.ledger_file, "w").close()

        self.server = None
        self.server_thread = None

    # ---------------- Clock ----------------
    def inc_clock(self):
        with self.clock_lock:
            self.clock += 1
            return self.clock

    def update_clock(self, remote_ts):
        with self.clock_lock:
            self.clock = max(self.clock, int(remote_ts)) + 1
            return self.clock

    # ---------------- Logging ----------------
    def log(self, msg):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{now}] [Node {self.node_id}] [clock={self.clock}] {msg}"
        print(line)
        with open(self.logfile, "a") as f:
            f.write(line + "\n")

    # ---------------- RPC Handlers ----------------
    def receive_request(self, ts, from_id):
        self.update_clock(ts)
        with self.queue_lock:
            self.request_queue.append((int(ts), str(from_id)))
            self.request_queue.sort()

        self.log(f"Received REQUEST from Node {from_id} (ts={ts}) Queue={self.request_queue}")

        do_reply = False
        with self.queue_lock:
            if not self.requesting:
                do_reply = True
            else:
                their = (int(ts), str(from_id))
                mine = (int(self.own_request_ts), str(self.node_id))
                if their < mine:
                    do_reply = True

        if do_reply:
            try:
                proxy = ServerProxy(self.peers[str(from_id)], allow_none=True)
                proxy.receive_reply(self.clock, self.node_id)
                self.log(f"Sent REPLY to Node {from_id}")
            except Exception as e:
                self.log(f"Error sending REPLY to Node {from_id}: {e}")
        else:
            with self.deferred_lock:
                self.deferred.add(str(from_id))
            self.log(f"Deferred REPLY to Node {from_id}")

        return True

    def receive_reply(self, ts, from_id):
        self.update_clock(ts)
        with self.replies_lock:
            self.replies_received.add(str(from_id))
        self.log(f"Received REPLY from Node {from_id}. Replies={self.replies_received}")
        return True

    def receive_release(self, ts, from_id):
        self.update_clock(ts)
        with self.queue_lock:
            self.request_queue = [x for x in self.request_queue if x[1] != str(from_id)]
        self.log(f"Received RELEASE from Node {from_id}. Queue={self.request_queue}")
        return True

    # ---------------- Core Logic ----------------
    def send_request_to_all(self):
        ts = self.inc_clock()
        self.own_request_ts = ts
        with self.queue_lock:
            self.request_queue.append((int(ts), str(self.node_id)))
            self.request_queue.sort()
        self.log(f"Broadcasting REQUEST ts={ts}")

        for pid, url in self.peers.items():
            try:
                proxy = ServerProxy(url, allow_none=True)
                proxy.receive_request(ts, self.node_id)
            except Exception as e:
                self.log(f"Error sending REQUEST to Node {pid}: {e}")

    def send_release_to_all(self):
        ts = self.inc_clock()
        with self.queue_lock:
            self.request_queue = [x for x in self.request_queue if x[1] != str(self.node_id)]
        self.log(f"Broadcasting RELEASE ts={ts}")

        for pid, url in self.peers.items():
            try:
                proxy = ServerProxy(url, allow_none=True)
                proxy.receive_release(ts, self.node_id)
            except Exception as e:
                self.log(f"Error sending RELEASE to Node {pid}: {e}")

        # Send deferred replies
        with self.deferred_lock:
            deferred = list(self.deferred)
            self.deferred.clear()
        for pid in deferred:
            try:
                proxy = ServerProxy(self.peers[pid], allow_none=True)
                proxy.receive_reply(self.clock, self.node_id)
                self.log(f"Sent deferred REPLY to Node {pid}")
            except Exception as e:
                self.log(f"Error sending deferred REPLY to Node {pid}: {e}")

    def can_enter_cs(self):
        with self.replies_lock, self.queue_lock:
            all_replied = len(self.replies_received) == len(self.peers)
            smallest = (
                self.request_queue
                and self.request_queue[0] == (int(self.own_request_ts), str(self.node_id))
            )
            return self.requesting and all_replied and smallest

    def critical_section(self):
        self.log(">>> ENTERING CRITICAL SECTION <<<")
        with open(self.ledger_file, "a") as f:
            f.write(f"Node {self.node_id} ENTERED CS at {datetime.now()}\n")
        time.sleep(2)
        with open(self.ledger_file, "a") as f:
            f.write(f"Node {self.node_id} EXITING CS at {datetime.now()}\n")
        self.log("<<< EXITING CRITICAL SECTION >>>")

    def request_cs_and_wait(self):
        with self.replies_lock:
            self.replies_received = set()
        self.requesting = True
        self.send_request_to_all()
        self.log("Waiting for all REPLIES and queue order...")

        while not self.can_enter_cs():
            time.sleep(0.2)

        self.critical_section()

        self.requesting = False
        self.replies_received = set()
        self.send_release_to_all()

    # ---------------- RPC Server ----------------
    def start_rpc_server(self, host, port):
        def serve():
            server = SimpleXMLRPCServer((host, port), allow_none=True, logRequests=False)
            server.register_function(self.receive_request, "receive_request")
            server.register_function(self.receive_reply, "receive_reply")
            server.register_function(self.receive_release, "receive_release")
            self.server = server
            self.log(f"RPC server started on {host}:{port}")
            server.serve_forever()

        t = threading.Thread(target=serve, daemon=True)
        t.start()
        self.server_thread = t

    # ---------------- Simulation ----------------
    def simulate(self, request_count=3, min_delay=2, max_delay=6):
        for i in range(request_count):
            delay = random.randint(min_delay, max_delay)
            self.log(f"Sleeping {delay}s before CS request {i+1}/{request_count}")
            time.sleep(delay)
            self.request_cs_and_wait()
        self.log("Simulation complete.")

# ---------------- Helpers ----------------
def read_config(path):
    with open(path, "r") as f:
        return json.load(f)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--requests", type=int, default=3)
    args = parser.parse_args()

    cfg = read_config(args.config)
    node_id = str(args.id)
    if node_id not in cfg:
        print("Node ID not found in config")
        sys.exit(1)

    url = cfg[node_id]
    parts = url.replace("http://", "").split(":")
    host = parts[0]
    port = int(parts[1])

    node = LamportNode(node_id, url, cfg)
    node.start_rpc_server(host, port)
    time.sleep(1)
    node.simulate(request_count=args.requests)

if __name__ == "__main__":
    main()
