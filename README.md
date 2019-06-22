# baremetal-upi-sandbox
OCP4.x BareMetal UPI (User Provided Infrastructure) Virtual Sandbox

![](https://trainingmaterials4423.s3.amazonaws.com/baremetal-upi-sandbox.png)


## Introduction
The Baremetal UPI Sandbox is a fun way to get a OCP 4.x baremetal install running on your local system. It currently uses [VirtualBox](https://www.virtualbox.org), [Vagrant](http://vagrantup.com), [Dnsmasq](https://www.thekelleys.org.uk/dnsmasq/doc.html), [Matchbox](https://github.com/poseidon/matchbox), [Terraform](https://www.terraform.io), [CoreDNS](https://coredns.io), and [HA Proxy](https://haproxy.org). It is for educational purposes only.

## TODO
* Consolidate to single Vagrantfile
* IPMI support

## Credits
Special thanks to [Yolanda Robla Mota](https://github.com/yrobla) for all the work on [https://github.com/redhat-nfvpe/upi-rt](https://github.com/redhat-nfvpe/upi-rt). 

Also check out:  
[https://github.com/e-minguez/ocp4-upi-bm-pxeless-staticips](https://github.com/e-minguez/ocp4-upi-bm-pxeless-staticips)  
[https://github.com/openshift/installer/tree/master/upi/metal](https://github.com/openshift/installer/tree/master/upi/metal)  
[https://docs.openshift.com/container-platform/4.1/installing/installing_bare_metal/installing-bare-metal.html](https://docs.openshift.com/container-platform/4.1/installing/installing_bare_metal/installing-bare-metal.html)
