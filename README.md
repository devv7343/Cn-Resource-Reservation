# Network Resource Reservation System (TCP + SDN)

Computer Networks mini project (Project 15), PES University.
Team: Devansh Singh Yadav (PES2UG25CS159), Chitra Likith Kumar (PES2UG25CS142), Chinmay Shridhar Naik (PES2UG25CS139).
Guide: Sharavana K

## What it does
Clients request bandwidth between hosts over TCP. The reservation server checks capacity and conflicts,
then asks the Ryu SDN controller (REST API) to install an OpenFlow flow rule and meter that limits the flow
to the reserved rate. Reservations are removed on cancel or expiry.

## Structure
- topology/topo.py : Mininet topology (3 hosts, 1 switch, link to the server)
- server/server.py : TCP reservation server (reserve, cancel, query, expiry)
- client/client.py : TCP client
- results/log.csv : event log written by the server

## Environment
Windows with WSL2, Ubuntu 22.04. Run every window with: wsl -d Ubuntu-22.04

## Setup
    sudo apt update
    sudo apt upgrade -y
    sudo apt install mininet openvswitch-switch iperf git python3-pip python3-venv tcpdump ethtool -y
    sudo service openvswitch-switch start
    python3 -m venv ~/cn-env
    source ~/cn-env/bin/activate
    pip install eventlet==0.33.3 ryu
    pip install dnspython==2.2.1
    sed -i 's/from eventlet.wsgi import ALREADY_HANDLED/ALREADY_HANDLED = []/' ~/cn-env/lib/python3.10/site-packages/ryu/app/wsgi.py

Notes on the fixes: the eventlet and dnspython versions and the sed patch are needed for Ryu 4.34 on Python 3.10.
WSL2 has no Open vSwitch kernel module, so the switch uses the user-space datapath, and checksum offload
is turned off on the host interfaces (done in topo.py) or TCP times out.

## Run (3 windows, in this order)
Window 1, controller:

    source ~/cn-env/bin/activate
    ryu-manager --ofp-tcp-listen-port 6653 ryu.app.simple_switch_13 ryu.app.ofctl_rest

Window 2, network (do not run "sudo mn -c" while Ryu is running, it kills Ryu):

    sudo mn -c
    cd ~/cn-project
    sudo python3 topology/topo.py

Window 3, reservation server:

    cd ~/cn-project
    python3 server/server.py

## Tests (at the mininet> prompt)
    h2 iperf -s &
    h1 iperf -c 10.0.0.2 -t 5
    h1 python3 client/client.py reserve 10.0.0.1 10.0.0.2 6 30
    h1 iperf -c 10.0.0.2 -t 5
    h3 python3 client/client.py reserve 10.0.0.3 10.0.0.2 6 30
    h3 python3 client/client.py reserve 10.0.0.3 10.0.0.2 4 30
    h1 python3 client/client.py query
    h1 python3 client/client.py cancel 1

## Results (measured)
- h1 to h2 iperf without a reservation: 1.74 Gbits/sec
- h1 to h2 iperf after a 6 Mbps reservation was accepted: 6.13 Mbits/sec
- A second 6 Mbps request to h2 was rejected (insufficient capacity); a 4 Mbps request was accepted.
- Cancel and expiry removed the rule and meter from the switch.

## Not implemented yet
Link-failure rerouting, port-statistics monitoring, and the multi-load comparison.
