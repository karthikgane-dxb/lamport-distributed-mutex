# Lamport Distributed Mutual Exclusion (Python Simulation)

## 🎯 Objective
This project simulates **Lamport’s Distributed Mutual Exclusion Algorithm** using Python and XML-RPC.

The goal is to demonstrate that multiple distributed nodes (processes) can coordinate access to a shared resource (Critical Section) **without conflicts**, ensuring:
- **Mutual Exclusion** – only one node enters the Critical Section at a time.
- **Fairness** – access is granted in the order of Lamport timestamps.
- **Coordination via RPC** – all communication happens using Remote Procedure Calls.

---

## ⚙️ Implementation Overview
- Implemented in **Python 3** using the `xmlrpc` library.
- Each node runs as an independent process (simulated in separate terminals).
- Nodes exchange three message types:
  1. **REQUEST** – asking permission to enter the Critical Section  
  2. **REPLY** – granting permission  
  3. **RELEASE** – announcing exit from the Critical Section
- The shared resource is simulated with a text file: `shared_ledger.txt`.

---

## 💻 How to Run
1. Open three terminal windows (or command prompts).
2. Navigate to the project folder in each:
   ```bash
   cd "C:\Users\karth\OneDrive\Desktop\Lamport-Assignment 1"
   Start each node in a separate terminal:
python node.py --id 1 --config nodes_config.json
python node.py --id 2 --config nodes_config.json
python node.py --id 3 --config nodes_config.json
Example output
[Node 1] REQUESTING Critical Section at ts=1
[Node 1] >>> ENTERING CRITICAL SECTION <<<
[Node 1] <<< EXITING CRITICAL SECTION >>>
[Node 2] >>> ENTERING CRITICAL SECTION <<<
[Node 2] <<< EXITING CRITICAL SECTION >>>
