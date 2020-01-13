# Setting up UPI Sandbox via CloudLab
__#TODO automation of cloudlab experiment deployment and server hostname returned for Ansible initial setup__

## Prerequisites

We are going to use an Ansible playbook for ease of use and organization. We need to install Ansible then download and run the playbook.

### openlab user

```
# re-partition sda to use all space
sed -e 's/\s*\([\+0-9a-zA-Z]*\).*/\1/' << EOF | sudo fdisk /dev/sda
  o # clear the in memory partition table
  n # new partition
  p # primary partition
  1 # partition number 1
    # default - start at beginning of disk
    # default - use all of the disk
  a # make a partition bootable
  p # print the in-memory partition table
  w # write the partition table
  q # and we're done
EOF

# create partition on sdb
sudo parted -s -a opt -- /dev/sdb mklabel gpt mkpart primary ext4 1MiB 100%
sudo mkfs.ext4 /dev/sdb1
#TODO get the UUID of /dev/sdb1 and add it to fstab
DEV_SDB1_UUID=$(sudo blkid -o value -s UUID /dev/sdb1)
cat /etc/fstab > fstab
cat << EOF >> fstab
UUID=${DEV_SDB1_UUID}    /var/lib/libvirt/images    ext4    defaults    0    0
EOF
sudo mv fstab /etc/fstab

# reboot the server
sudo reboot

# extend the sda1 partition
sudo resize2fs /dev/sda1

# add policy for libvirt allowing regular users
sudo usermod -aG libvirt openlab
sudo mkdir -p /etc/polkit-1/rules.d/
cat << EOF >> 49-org.libvirt.unix.manager.rules
/* Allow users in kvm group to manage the libvirt
daemon without authentication */
polkit.addRule(function(action, subject) {
    if (action.id == "org.libvirt.unix.manage" &&
        subject.isInGroup("libvirt")) {
            return polkit.Result.YES;
    }
});
EOF
sudo mv 49-org.libvirt.unix.manager.rules /etc/polkit-1/rules.d/

# fix issue with NetworkManager and Libvirt bridging
cat << EOF >> 99-bridge.rules
ACTION=="add", SUBSYSTEM=="module", KERNEL=="br_netfilter", RUN+="/lib/systemd/systemd-sysctl --prefix=/net/bridge"
EOF
sudo mv 99-bridge.rules /etc/udev/rules.d/

cat << EOF >> 98-bridge.conf
net.bridge.bridge-nf-call-ip6tables = 0
net.bridge.bridge-nf-call-iptables = 0
net.bridge.bridge-nf-call-arptables = 0
EOF
sudo mv 98-bridge.conf /etc/sysctl.d/


# install required packages
sudo add-apt-repository -y ppa:vbernat/haproxy-2.1
sudo apt update
## pip
sudo apt install -y python-dev python3-dev
sudo bash -c 'python <(curl -sk https://bootstrap.pypa.io/get-pip.py)'
## virtualization
sudo apt install -y qemu-kvm libvirt-daemon libvirt-daemon-system network-manager
sudo apt install -y qemu libvirt-clients ebtables dnsmasq-base haproxy expect 
sudo apt install -y libxslt-dev libxml2-dev libvirt-dev zlib1g-dev ruby-dev ipmitool ipmiutil
## virtualbmc
sudo pip install virtualbmc

# add openlab user to libvirt group
sudo usermod -aG libvirt openlab

# get openshift binaries (this should be relevant to the version of openshift you want to install)
#TODO check for version programmatically
wget https://mirror.openshift.com/pub/openshift-v4/clients/ocp-dev-preview/latest/openshift-install-linux-4.4.0-0.nightly-2019-12-20-210709.tar.gz
wget https://mirror.openshift.com/pub/openshift-v4/clients/ocp-dev-preview/latest/openshift-client-linux-4.4.0-0.nightly-2019-12-20-210709.tar.gz

tar xzf openshift-client-*
tar xzf openshift-install-*
sudo mv kubectl oc openshift-install /usr/local/bin

# install upstream golang
#TODO check for version programmatically
wget https://dl.google.com/go/go1.13.5.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.13.5.linux-amd64.tar.gz

# get coredns binaries
wget https://github.com/coredns/coredns/releases/download/v1.6.6/coredns_1.6.6_linux_amd64.tgz
tar xzf coredns_1.6.6_linux_amd64.tgz
sudo mv coredns /usr/local/bin

# get matchbox binaries
wget https://github.com/poseidon/matchbox/releases/download/v0.8.3/matchbox-v0.8.3-linux-amd64.tar.gz
tar xzf matchbox-v0.8.3-linux-amd64.tar.gz
sudo mv matchbox-v0.8.3-linux-amd64/matchbox /usr/local/bin

# get terraform binaries
wget https://releases.hashicorp.com/terraform/0.12.18/terraform_0.12.18_linux_amd64.zip
unzip terraform_0.12.18_linux_amd64.zip
sudo mv terraform /usr/local/bin

wget https://raw.githubusercontent.com/Bash-it/bash-it/master/completion/available/virsh.completion.bash
sudo mv virsh.completion.bash /etc/bash_completion.d/virsh

# change to root user
sudo -i

# install upstream vagrant and vagrant-libvirt
#TODO check for version programmatically
wget https://releases.hashicorp.com/vagrant/2.2.6/vagrant_2.2.6_x86_64.deb
dpkg -i vagrant_2.2.6_x86_64.deb
vagrant plugin install vagrant-libvirt

# setup the pxe_network
cat << EOF >> pxe_network.xml
<network>
  <name>pxe_network</name>
  <forward mode='nat'>
    <nat>
      <port start='1024' end='65535'/>
    </nat>
  </forward>
  <ip address='192.168.0.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='192.168.0.150' end='192.168.0.200'/>
    </dhcp>
  </ip>
</network>
EOF
virsh net-define pxe_network.xml
virsh net-autostart pxe_network
virsh net-start pxe_network

# matchbox domain
# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  config.vm.define :matchbox do |matchbox|

    matchbox.vm.box = "fedora/31-cloud-base"
    matchbox.vm.hostname = "matchbox"
    matchbox.vm.network "private_network", :ip => "192.168.0.254", :libvirt__network_name => "pxe_network"

    matchbox.vm.provider :libvirt do |vb|
      vb.management_network_name = "default"
      vb.management_network_address = "192.168.122.0/24"
      vb.memory = "2048"
      vb.cpus = "2"
    end

    matchbox.vm.provision "shell", path: "config/setup.sh"
  end
end

# working Vagrantfile for PXE
# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  config.vm.define :bootstrap do |bootstrap|

    bootstrap.vm.provider :libvirt do |lv|
      lv.mgmt_attach = false
      lv.memory = "2048"
      lv.cpus = "2"
      lv.storage :file, :device => 'vda', :size => '40G', :type => 'qcow2'
    end

    bootstrap.vm.hostname = "bootstrap"
    bootstrap.vm.network :private_network,
      :ip => "192.168.0.2",
      :mac => "08:00:27:3d:80:e2",
      :libvirt__netmask => "255.255.255.0",
      :libvirt__network_name => "pxe_network"
  end
end

# get github repos
git clone https://github.com/mrhillsman/baremetal-upi-sandbox
git clone https://github.com/mrhillsman/upi-rt

# change CLUSTER_DOMAIN, CLUSTER_NAME, PULL_SECRET, and SSH_KEY

# NOTES
we need to be able to get the first IP of the pxe_network to set it in resolv.conf for matchbox node
for libvirt, no box pxe is ideal, quicker, less disk usage however network config does not work...so how does it pxe?

install cockpit
  apt-get install cockpit cockpit-docker cockpit-packagekit cockpit-machines
  vim /etc/cockpit/cockpit.conf
  [WebService]
  AllowUnencrypted = true
  systemctl restart cockpit.service cockpit.socket

```
