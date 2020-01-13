# baremetal-upi-sandbox
OCP4.x BareMetal UPI (User Provided Infrastructure) Virtual Sandbox

![](https://trainingmaterials4423.s3.amazonaws.com/baremetal-upi-sandbox.png)


## Introduction
The Baremetal UPI Sandbox is a fun way to get a OCP 4.x baremetal install running on a Linux server. It currently uses [libvirt](https://www.libvirt.org), [Vagrant](http://vagrantup.com), [dnsmasq](https://www.thekelleys.org.uk/dnsmasq/doc.html), [matchbox](https://github.com/poseidon/matchbox), [Terraform](https://www.terraform.io), [CoreDNS](https://coredns.io), and [HA Proxy](https://haproxy.org). It is for educational purposes only.

## Instructions
### Prerequisites

### Using mksetup.py
```shell
root@host:~/baremetal-upi-sandbox# ./mksetup.py -h
usage: mksetup.py [-h] [-d CLUSTER_DOMAIN] [-n CLUSTER_NAME]
                  [-m CLUSTER_MASTERS] [-w CLUSTER_WORKERS]
                  [-k CLUSTER_SSH_KEY] [-s CLUSTER_PULL_SECRET]

Pythonn script to create matchbox node setup script

optional arguments:
  -h, --help            show this help message and exit
  -d CLUSTER_DOMAIN, --cluster-domain CLUSTER_DOMAIN
                        Domain of cluster; i.e. example.com
  -n CLUSTER_NAME, --cluster-name CLUSTER_NAME
                        Cluster name to be used before domain
  -m CLUSTER_MASTERS, --masters CLUSTER_MASTERS
                        Number of masters to create
  -w CLUSTER_WORKERS, --workers CLUSTER_WORKERS
                        Number of workers to create
  -k CLUSTER_SSH_KEY, --ssh-key CLUSTER_SSH_KEY
                        SSH key to inject
  -s CLUSTER_PULL_SECRET, --pull-secret CLUSTER_PULL_SECRET
                        Pull secret for Red Hat registry
```

### Using launcher.py

###

## TODO
* Consolidate to single Vagrantfile
* IPMI support

## Credits
Special thanks to [Matthew Dorn](https://github.com/madorn) and [Yolanda Robla Mota](https://github.com/yrobla) for all the work on [https://github.com/redhat-nfvpe/upi-rt](https://github.com/redhat-nfvpe/upi-rt). 

Also check out:  
[https://github.com/e-minguez/ocp4-upi-bm-pxeless-staticips](https://github.com/e-minguez/ocp4-upi-bm-pxeless-staticips)  
[https://github.com/openshift/installer/tree/master/upi/metal](https://github.com/openshift/installer/tree/master/upi/metal)  
[https://docs.openshift.com/container-platform/4.1/installing/installing_bare_metal/installing-bare-metal.html](https://docs.openshift.com/container-platform/4.1/installing/installing_bare_metal/installing-bare-metal.html)
