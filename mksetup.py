#!/usr/bin/env python

import argparse
parser = argparse.ArgumentParser(description='Pythonn script to create matchbox node setup script')
parser.add_argument('-d', '--cluster-domain', action='store', dest='cluster_domain', type=str, default='local.lab', help='Domain of cluster; i.e. example.com')
parser.add_argument('-n', '--cluster-name', action='store', dest='cluster_name', type=str, default='os', help='Cluster name to be used before domain')
parser.add_argument('-m', '--masters', action='store', dest='cluster_masters', type=int, default=1, help='Number of masters to create')
parser.add_argument('-w', '--workers', action='store', dest='cluster_workers', type=int, default=1, help='Number of workers to create')
parser.add_argument('-k', '--ssh-key', action='store', dest='cluster_ssh_key', type=str, default='/root/.ssh/id_rsa.pub', help='SSH key to inject')
parser.add_argument('-s', '--pull-secret', action='store', dest='cluster_pull_secret', type=str, default='/root/.pullsecret', help='Pull secret for Red Hat registry')

args = parser.parse_args()

if args.cluster_masters < 0 or args.cluster_masters > 9:
     parser.error('The number of masters must be a positive integer less than or equal to 9.')

if args.cluster_workers < 0 or args.cluster_workers > 30:
     parser.error('The number of masters must be a positive integer less than or equal to 30.')

matchbox_ip='192.168.0.254'
vip_ip='192.168.0.254'
host_ip="192.168.0.1"
bootstrap_ip='192.168.0.2'
bootstrap_mac='08:00:27:3D:80:00'
bootstrap_ipmi_user='admin'
bootstrap_ipmi_pass='password'
bootstrap_ipmi_port='10000'
cluster_masters=args.cluster_masters
cluster_workers=args.cluster_workers
openshift_install_version=
openshift_client_version=
rhcos_initrd=
rhcos_kernel=
rhcos_osimage=

print("""\
#!/usr/bin/env bash

set -x
""")

print("""\
export HOST_IP={}
export CLUSTER_DOMAIN={}
export CLUSTER_NAME={}
export MATCHBOX_IP={}
export VIP_IP={}
""".format(host_ip, args.cluster_domain, args.cluster_name, matchbox_ip, vip_ip))

print("""\
export BOOTSTRAP_IP={}
export BOOTSTRAP_MAC={}
export BOOTSTRAP_IPMI_USER={}
export BOOTSTRAP_IPMI_PASS={}
export BOOTSTRAP_IPMI_PORT={}
""".format(bootstrap_ip, bootstrap_mac, bootstrap_ipmi_user, bootstrap_ipmi_pass, bootstrap_ipmi_port))

for master in range(cluster_masters):
    print("export MASTER{}_IP=192.168.0.{}".format(master, 50+master))
    print("export MASTER{}_MAC=08:00:27:3d:80:{}".format(master, hex(50+master).lstrip("0x")))
    print("export MASTER{}_IPMI_USER=admin".format(master))
    print("export MASTER{}_IPMI_PASS=password".format(master))
    print("export MASTER{}_IPMI_PORT={}".format(master, 10050+master))

for worker in range(cluster_workers):
    print("export WORKER{}_IP=192.168.0.{}".format(worker, 100+worker))
    print("export WORKER{}_MAC=08:00:27:3d:90:{}".format(worker, hex(50+worker).lstrip("0x")))
    print("export WORKER{}_IPMI_USER=admin".format(worker))
    print("export WORKER{}_IPMI_PASS=password".format(worker))
    print("export WORKER{}_IPMI_PORT={}".format(worker, 10100+worker))

with open(args.cluster_ssh_key, "r") as f:
    ssh_key = f.read()
    print("\nexport SSH_KEY='{}'".format(ssh_key))

with open(args.cluster_pull_secret, "r") as f:
    pull_secret = f.read().rstrip('\n')
    print("\nexport PULL_SECRET='{}'".format(pull_secret))

print("""
# disable firewalld
sudo systemctl stop firewalld
sudo systemctl disable firewalld

# update
sudo dnf check-update

# install stuff
sudo dnf install -y podman bind-utils jq wget unzip ipmitool

# create haproxy directory
sudo -u vagrant mkdir /home/vagrant/haproxy

# create haproxy config
sudo -u vagrant cat > /home/vagrant/haproxy/haproxy.cfg << EOF
defaults
    mode                    http
    log                     global
    option                  httplog
    option                  dontlognull
    option forwardfor       except 127.0.0.0/8
    option                  redispatch
    retries                 3
    timeout http-request    10s
    timeout queue           1m
    timeout connect         10s
    timeout client          300s
    timeout server          300s
    timeout http-keep-alive 10s
    timeout check           10s
    maxconn                 20000

# Useful for debugging, dangerous for production
listen stats
    bind :9000
    mode http
    stats enable
    stats uri /

frontend openshift-api-server
    bind *:6443
    default_backend openshift-api-server
    mode tcp
    option tcplog

backend openshift-api-server
    balance source
    mode tcp
    server bootstrap ${BOOTSTRAP_IP}:6443 check\
""")

for master in range(cluster_masters):
    print("""\
    server master{0} ${{MASTER{0}_IP}}:6443 check\
""".format(master))

print("""
frontend machine-config-server
    bind *:22623
    default_backend machine-config-server
    mode tcp
    option tcplog

backend machine-config-server
    balance source
    mode tcp
    server bootstrap ${BOOTSTRAP_IP}:22623 check\
""")

for master in range(cluster_masters):
    print("""\
    server master{0} ${{MASTER{0}_IP}}:22623 check\
""".format(master))

print("""
frontend ingress-http
    bind *:80
    default_backend ingress-http
    mode tcp
    option tcplog

backend ingress-http
    balance source
    mode tcp\
""")
for worker in range(cluster_workers):
    print("""\
    server worker{0} ${{WORKER{0}_IP}}:80 check\
""".format(worker))

print("""
frontend ingress-https
    bind *:443
    default_backend ingress-https
    mode tcp
    option tcplog

backend ingress-https
    balance source
    mode tcp\
""")

for worker in range(cluster_workers):
    print("""\
    server worker{0} ${{WORKER{0}_IP}}:443 check\
""".format(worker))

print("""\
EOF

# run haproxy container
sudo podman run -d --rm \\
  -p 9000:9000 -p 22623:22623 -p 6443:6443 -p 80:80 -p 443:443 \\
  -v /home/vagrant/haproxy/haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:Z \\
  --name haproxy \\
  haproxy:alpine

# install terraform + matchbox provider
sudo -u vagrant wget -v https://releases.hashicorp.com/terraform/0.12.2/terraform_0.12.2_linux_amd64.zip
sudo unzip terraform_0.12.2_linux_amd64.zip -d /bin

sudo -u vagrant wget -v https://github.com/poseidon/terraform-provider-matchbox/releases/download/v0.3.0/terraform-provider-matchbox-v0.3.0-linux-amd64.tar.gz
sudo -u vagrant tar xzf terraform-provider-matchbox-v0.3.0-linux-amd64.tar.gz
sudo -u vagrant cat <<EOF | tee /home/vagrant/.terraformrc
providers {
  matchbox = "/home/vagrant/terraform-provider-matchbox-v0.3.0-linux-amd64/terraform-provider-matchbox"
}
EOF


# clone matchbox repo
sudo -u vagrant git clone https://github.com/poseidon/matchbox

# generate matchbox certs
pushd matchbox/scripts/tls
sudo -u vagrant SAN=DNS.1:matchbox.${CLUSTER_DOMAIN},IP.1:${MATCHBOX_IP} ./cert-gen
sudo -u vagrant cp ca.crt server.crt server.key ../../examples/etc/matchbox
sudo -u vagrant mkdir -p /home/vagrant/.matchbox
sudo -u vagrant cp client.crt client.key ca.crt /home/vagrant/.matchbox/
popd

# create matchbox assets directoy
sudo -u vagrant mkdir -p /home/vagrant/matchbox/examples/assets

# run matchbox
export ASSETS_DIR="/home/vagrant/matchbox/examples/assets"
export CONFIG_DIR="/home/vagrant/matchbox/examples/etc/matchbox"
export MATCHBOX_ARGS="-rpc-address=0.0.0.0:8081"

sudo podman run -d --rm --name matchbox \\
  -d \\
  -p 8080:8080 \\
  -p 8081:8081 \\
  -v $CONFIG_DIR:/etc/matchbox:Z \\
  -v $ASSETS_DIR:/var/lib/matchbox/assets:Z \\
  $DATA_MOUNT \\
  quay.io/poseidon/matchbox:latest -address=0.0.0.0:8080 -log-level=debug $MATCHBOX_ARGS

# run dnsmasq
sudo podman run -d --rm --cap-add=NET_ADMIN --net=host \\
  --name=dnsmasq \\
  quay.io/poseidon/dnsmasq -d -q \\
  --port=0 \\
  --interface=eth1 \\
  -z \\
  --dhcp-range=192.168.0.2,192.168.0.253 \\
  --dhcp-option=3,192.168.0.254 \\
  --dhcp-option=6,192.168.0.254 \\
  --dhcp-match=set:bios,option:client-arch,0 \\
  --dhcp-boot=tag:bios,undionly.kpxe \\
  --dhcp-match=set:efi32,option:client-arch,6 \\
  --dhcp-boot=tag:efi32,ipxe.efi \\
  --dhcp-match=set:efibc,option:client-arch,7 \\
  --dhcp-boot=tag:efibc,ipxe.efi \\
  --dhcp-match=set:efi64,option:client-arch,9 \\
  --dhcp-boot=tag:efi64,ipxe.efi \\
  --log-queries \\
  --log-dhcp \\
  --dhcp-userclass=set:ipxe,iPXE \\
  --dhcp-boot=tag:ipxe,http://${MATCHBOX_IP}:8080/boot.ipxe \\
  --enable-tftp \\
  --tftp-root=/var/lib/tftpboot \\
  --tftp-no-blocksize \\
  --dhcp-boot=pxelinux.0 \\
  --dhcp-host=08:00:27:3D:80:00,192.168.0.2,bootstrap \\""")

for master in range(cluster_masters):
    print("  --dhcp-host=${{MASTER{0}_MAC}},${{MASTER{0}_IP}},master{0} \\".format(master))

for worker in range(cluster_workers):
    if worker == cluster_workers-1:
        print("  --dhcp-host=${{WORKER{0}_MAC}},${{WORKER{0}_IP}},worker{0}".format(worker))
    else:
        print("  --dhcp-host=${{WORKER{0}_MAC}},${{WORKER{0}_IP}},worker{0} \\".format(worker))

print("""
# setup coredns
sudo -u vagrant mkdir -p /home/vagrant/coredns

sudo -u vagrant cat <<EOF | tee /home/vagrant/coredns/db.${CLUSTER_DOMAIN}
\\$ORIGIN ${CLUSTER_DOMAIN}.
\\$TTL 10800      ; 3 hours
@       3600 IN SOA sns.dns.icann.org. noc.dns.icann.org. (
                                2019010101 ; serial
                                7200       ; refresh (2 hours)
                                3600       ; retry (1 hour)
                                1209600    ; expire (2 weeks)
                                3600       ; minimum (1 hour)
                                )

""")

for master in range(cluster_masters):
    print("""\
_etcd-server-ssl._tcp.${{CLUSTER_NAME}}.${{CLUSTER_DOMAIN}}. 8640 IN    SRV 0 10 2380 etcd{0}.${{CLUSTER_NAME}}.${{CLUSTER_DOMAIN}}.
""".format(master))

print("""\
api.${CLUSTER_NAME}.${CLUSTER_DOMAIN}.              A ${VIP_IP}
api-int.${CLUSTER_NAME}.${CLUSTER_DOMAIN}.          A ${VIP_IP}
${CLUSTER_NAME}-bootstrap.${CLUSTER_DOMAIN}.        A ${BOOTSTRAP_IP}
""")

for master in range(cluster_masters):
    print("""\
${{CLUSTER_NAME}}-master{0}.${{CLUSTER_DOMAIN}}.    A ${{MASTER{0}_IP}}
etcd{0}.${{CLUSTER_NAME}}.${{CLUSTER_DOMAIN}}.      IN  CNAME ${{CLUSTER_NAME}}-master{0}.${{CLUSTER_DOMAIN}}.\
""".format(master))

for worker in range(cluster_workers):
    print("""\
${{CLUSTER_NAME}}-worker{0}.${{CLUSTER_DOMAIN}}.    A ${{WORKER{0}_IP}}\
""".format(worker))

print("""\

\\$ORIGIN apps.${CLUSTER_NAME}.${CLUSTER_DOMAIN}.
*    A    ${VIP_IP}
EOF

sudo -u vagrant cat <<EOF | tee /home/vagrant/coredns/Corefile
.:53 {
    log
    errors
    forward . 8.8.8.8
}

${CLUSTER_DOMAIN}:53 {
    log
    errors
    file /etc/coredns/db.${CLUSTER_DOMAIN}
    debug
}
EOF


# turn off systemd-resolved
sudo systemctl disable systemd-resolved
sudo systemctl stop systemd-resolved

# remove symlinked resolv.conf
sudo rm /etc/resolv.conf

# create new resolv.conf
cat <<EOF | sudo tee /etc/resolv.conf
nameserver ${HOST_IP}
EOF

# none: NetworkManager will not modify resolv.conf.
sudo sed -i "s|#plugins=ifcfg-rh,ibft|#plugins=ifcfg-rh,ibft\\ndns=none|g" /etc/NetworkManager/NetworkManager.conf
sudo systemctl restart NetworkManager

# run coredns
sudo podman run -d --rm --name coredns \\
  -d \\
  -p 53:53 \\
  -p 53:53/udp \\
  -v /home/vagrant/coredns:/etc/coredns:z \\
  coredns/coredns:latest \\
  -conf /etc/coredns/Corefile

# create an install dir
sudo -u vagrant mkdir -p /tmp/baremetal

# create install-config.yaml
sudo -u vagrant cat <<EOF | tee /tmp/baremetal/install-config.yaml
 apiVersion: v1
 baseDomain: ${CLUSTER_DOMAIN}
 compute:
 - name: worker
   replicas: 1
 controlPlane:
   name: master
   platform: {}
   replicas: 1
 metadata:
   name: ${CLUSTER_NAME}
 networking:
   clusterNetwork:
   - cidr: 10.128.0.0/14
     hostPrefix: 23
   machineCIDR: 10.0.0.0/16
   networkType: OpenShiftSDN
   serviceNetwork:
   - 172.30.0.0/16
 platform:
   none: {}
 pullSecret: '${PULL_SECRET}'
 sshKey: |
   ${SSH_KEY}
EOF

# download and setup openshift-install
sudo -u vagrant wget -v https://mirror.openshift.com/pub/openshift-v4/clients/ocp/4.1.0/openshift-install-linux-4.1.0.tar.gz
sudo -u vagrant tar xzf openshift-install-linux-4.1.0.tar.gz
sudo -u vagrant /home/vagrant/openshift-install create manifests --dir=/tmp/baremetal
sudo -u vagrant /home/vagrant/openshift-install create ignition-configs --dir=/tmp/baremetal

# download and setup openshift client
sudo -u vagrant wget -v https://mirror.openshift.com/pub/openshift-v4/clients/ocp/4.1.0/openshift-client-linux-4.1.0.tar.gz
sudo -u vagrant tar xzf openshift-client-linux-4.1.0.tar.gz

# fetch RHCOS
sudo -u vagrant wget -v https://mirror.openshift.com/pub/openshift-v4/dependencies/rhcos/4.1/4.1.0/rhcos-4.1.0-x86_64-installer-initramfs.img -O /home/vagrant/matchbox/examples/assets/rhcos-4.1.0-x86_64-installer-initramfs.img
sudo -u vagrant wget -v https://mirror.openshift.com/pub/openshift-v4/dependencies/rhcos/4.1/4.1.0/rhcos-4.1.0-x86_64-installer-kernel -O /home/vagrant/matchbox/examples/assets/rhcos-4.1.0-x86_64-installer-kernel
sudo -u vagrant wget -v https://mirror.openshift.com/pub/openshift-v4/dependencies/rhcos/4.1/4.1.0/rhcos-4.1.0-x86_64-metal-bios.raw.gz -O /home/vagrant/matchbox/examples/assets/rhcos-4.1.0-x86_64-metal-bios.raw.gz

# setup terraform for bootstrap + master
sudo -u vagrant mkdir -p /home/vagrant/matchbox/examples/terraform/ocp4
sudo -u vagrant git clone https://github.com/mrhillsman/upi-rt
sudo -u vagrant cp -r /home/vagrant/upi-rt/terraform/* /home/vagrant/matchbox/examples/terraform/ocp4
sudo -u vagrant cat <<EOF | tee /home/vagrant/matchbox/examples/terraform/ocp4/cluster/terraform.tfvars
cluster_domain = "${CLUSTER_DOMAIN}"
cluster_id= "${CLUSTER_NAME}"

matchbox_client_cert = "/home/vagrant/.matchbox/client.crt"
matchbox_client_key = "/home/vagrant/.matchbox/client.key"
matchbox_http_endpoint = "http://${MATCHBOX_IP}:8080"
matchbox_rpc_endpoint = "${MATCHBOX_IP}:8081"
matchbox_trusted_ca_cert = "/home/vagrant/matchbox/examples/etc/matchbox/ca.crt"

pxe_initrd_url = "assets/rhcos-4.1.0-x86_64-installer-initramfs.img"
pxe_kernel_url = "assets/rhcos-4.1.0-x86_64-installer-kernel"
pxe_os_image_url = "http://${VIP_IP}:8080/assets/rhcos-4.1.0-x86_64-metal-bios.raw.gz"

bootstrap_public_ipv4 = "${BOOTSTRAP_IP}"
bootstrap_mac_address = "${BOOTSTRAP_MAC}"
bootstrap_ipmi_host = "${HOST_IP}"
bootstrap_ipmi_user = "${BOOTSTRAP_IPMI_USER}"
bootstrap_ipmi_pass = "${BOOTSTRAP_IPMI_PASS}"
bootstrap_ipmi_port = "${BOOTSTRAP_IPMI_PORT}"
bootstrap_ign_file = "/tmp/baremetal/bootstrap.ign"
""")

for master in range(cluster_masters):
    print("""\
master_public_ipv4 = "${{MASTER{0}_IP}}"
master_mac_address = "${{MASTER{0}_MAC}}"
master_ipmi_host = "${{HOST_IP}}"
master_ipmi_user = "${{MASTER{0}_IPMI_USER}}"
master_ipmi_pass = "${{MASTER{0}_IPMI_PASS}}"
master_ipmi_port = "${{MASTER{0}_IPMI_PORT}}"
master_ign_file = "/tmp/baremetal/master.ign"
""".format(master))

if cluster_masters == 1:
    print("master_count = 1\nEOF")
else:
    print("master_count = {}\nEOF".format(cluster_masters))

print("""\
# setup terraform for worker
sudo -u vagrant cat <<EOF | tee /home/vagrant/matchbox/examples/terraform/ocp4/workers/terraform.tfvars
cluster_domain = "${CLUSTER_DOMAIN}"
cluster_id= "${CLUSTER_NAME}"

matchbox_client_cert = "/home/vagrant/.matchbox/client.crt"
matchbox_client_key = "/home/vagrant/.matchbox/client.key"
matchbox_http_endpoint = "http://${MATCHBOX_IP}:8080"
matchbox_rpc_endpoint = "${MATCHBOX_IP}:8081"
matchbox_trusted_ca_cert = "/home/vagrant/matchbox/examples/etc/matchbox/ca.crt"

pxe_initrd_url = "assets/rhcos-4.1.0-x86_64-installer-initramfs.img"
pxe_kernel_url = "assets/rhcos-4.1.0-x86_64-installer-kernel"
pxe_os_image_url = "http://${VIP_IP}:8080/assets/rhcos-4.1.0-x86_64-metal-bios.raw.gz"\
""")

for worker in range(cluster_workers):
    print("""\
worker_public_ipv4 = "${{WORKER{0}_IP}}"
worker_mac_address = "${{WORKER{0}_MAC}}"
worker_ipmi_host = "${{HOST_IP}}"
worker_ipmi_user = "${{WORKER{0}_IPMI_USER}}"
worker_ipmi_pass = "${{WORKER{0}_IPMI_PASS}}"
worker_ipmi_port = "${{WORKER{0}_IPMI_PORT}}"
worker_ign_file = "/tmp/baremetal/worker.ign"
""".format(worker))

if cluster_workers == 1:
    print("worker_count = 1\nEOF")
else:
    print("worker_count = {}\nEOF".format(cluster_workers))

print("""
sudo iptables -t nat -I POSTROUTING 1 -o eth0 -j MASQUERADE

# init and apply bootstrap/master
pushd /home/vagrant/matchbox/examples/terraform/ocp4/cluster
sudo -u vagrant terraform init
sudo -u vagrant terraform apply -auto-approve
popd

# init and apply worker
pushd /home/vagrant/matchbox/examples/terraform/ocp4/workers
sudo -u vagrant terraform init
sudo -u vagrant terraform apply -auto-approve
popd

cat <<EOF | sudo tee /etc/resolv.conf
nameserver ${VIP_IP}
EOF

echo "Manually 'vagrant up' the Bootstrap and Master nodes"

# Wait for bootstrapping to complete...
sudo -u vagrant /home/vagrant/openshift-install wait-for bootstrap-complete --dir=/tmp/baremetal --log-level debug

echo "Destroy Bootstrap and 'vagrant up' the Worker"

sleep 300

# Approve pending worker CSR request
export KUBECONFIG=/tmp/baremetal/auth/kubeconfig
/home/vagrant/oc get csr -ojson | jq -r '.items[] | select(.status == {} ) | .metadata.name' | xargs oc adm certificate approve

# Updating image-registry to emptyDir storage backend
/home/vagrant/oc patch configs.imageregistry.operator.openshift.io cluster --type merge --patch '{"spec":{"storage":{"emptyDir":{}}}}'

# Wait for install to complete...
sudo -u vagrant /home/vagrant/openshift-install wait-for install-complete --dir=/tmp/baremetal --log-level debug
""")
