from functools import partial
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController, Node
from mininet.cli import CLI
from mininet.log import setLogLevel

setLogLevel('info')
net = Mininet(controller=None,
              switch=partial(OVSSwitch, datapath='user', protocols='OpenFlow13'))
net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)
s1 = net.addSwitch('s1')
for i in (1, 2, 3):
    net.addHost('h%d' % i)
    net.addLink('h%d' % i, s1)

# reservation server lives in the root namespace, linked to s1
root = Node('root', inNamespace=False)
intf = net.addLink(root, s1).intf1
root.setIP('10.123.123.1/32', intf=intf)

net.start()
root.cmd('route add -net 10.0.0.0/24 dev ' + str(intf))
for h in net.hosts:
    h.cmd('ethtool -K %s-eth0 tx off rx off' % h.name)
root.cmd('ethtool -K %s tx off rx off' % intf)
CLI(net)
net.stop()
