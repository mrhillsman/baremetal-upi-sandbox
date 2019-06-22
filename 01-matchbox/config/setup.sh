#!/bin/bash
set +ex

# set variables
MATCHBOX_IP="192.168.0.254"
VIP_IP="192.168.0.254"
BOOTSTRAP_IP="192.168.0.2"
BOOTSTRAP_MAC="08:00:27:3D:80:E2"
MASTER_IP="192.168.0.3"
MASTER_MAC="08:00:27:3D:80:E3"
WORKER_IP="192.168.0.4"
WORKER_MAC="08:00:27:3D:80:E4"
CLUSTER_DOMAIN=example.org
CLUSTER_NAME=mycluster
PULL_SECRET=<your-pull-secret>
SSH_KEY=<your-public-ssh-key>

# disable firewalld
sudo systemctl stop firewalld
sudo systemctl disable firewalld

# update
sudo dnf check-update

# install stuff
sudo dnf install -y podman bind-utils jq

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
    server bootstrap ${BOOTSTRAP_IP}:6443 check
    server master-0 ${MASTER_IP}:6443 check

frontend machine-config-server
    bind *:22623
    default_backend machine-config-server
    mode tcp
    option tcplog

backend machine-config-server
    balance source
    mode tcp
    server bootstrap ${BOOTSTRAP_IP}:22623 check
    server master-0 ${MASTER_IP}:22623 check

frontend ingress-http
    bind *:80
    default_backend ingress-http
    mode tcp
    option tcplog

backend ingress-http
    balance source
    mode tcp
    server worker-0 ${WORKER_IP}:80 check

frontend ingress-https
    bind *:443
    default_backend ingress-https
    mode tcp
    option tcplog

backend ingress-https
    balance source
    mode tcp
    server worker-0 ${WORKER_IP}:443 check
EOF


# run haproxy container
sudo podman run -d --rm \
  -p 9000:9000 -p 22623:22623 -p 6443:6443 -p 80:80 -p 443:443 \
  -v /home/vagrant/haproxy/haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:Z \
  --name haproxy \
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
ASSETS_DIR="/home/vagrant/matchbox/examples/assets"
CONFIG_DIR="/home/vagrant/matchbox/examples/etc/matchbox"
MATCHBOX_ARGS="-rpc-address=0.0.0.0:8081"

sudo podman run -d --rm --name matchbox \
  -d \
  -p 8080:8080 \
  -p 8081:8081 \
  -v $CONFIG_DIR:/etc/matchbox:Z \
  -v $ASSETS_DIR:/var/lib/matchbox/assets:Z \
  $DATA_MOUNT \
  quay.io/poseidon/matchbox:latest -address=0.0.0.0:8080 -log-level=debug $MATCHBOX_ARGS

# run dnsmasq
sudo podman run -d --rm --cap-add=NET_ADMIN --net=host \
  --name=dnsmasq \
  quay.io/poseidon/dnsmasq -d -q \
  --port=0 \
  --interface=eth1 \
  -z \
  --dhcp-range=192.168.0.2,192.168.0.253 \
  --dhcp-option=3,192.168.0.254 \
  --dhcp-option=6,192.168.0.254 \
  --dhcp-match=set:bios,option:client-arch,0 \
  --dhcp-boot=tag:bios,undionly.kpxe \
  --dhcp-match=set:efi32,option:client-arch,6 \
  --dhcp-boot=tag:efi32,ipxe.efi \
  --dhcp-match=set:efibc,option:client-arch,7 \
  --dhcp-boot=tag:efibc,ipxe.efi \
  --dhcp-match=set:efi64,option:client-arch,9 \
  --dhcp-boot=tag:efi64,ipxe.efi \
  --log-queries \
  --log-dhcp \
  --dhcp-userclass=set:ipxe,iPXE \
  --dhcp-boot=tag:ipxe,http://${MATCHBOX_IP}:8080/boot.ipxe \
  --enable-tftp \
  --tftp-root=/var/lib/tftpboot \
  --tftp-no-blocksize \
  --dhcp-boot=pxelinux.0 \
  --dhcp-host=08:00:27:3D:80:E2,192.168.0.2,bootstrap \
  --dhcp-host=08:00:27:3D:80:E3,192.168.0.3,master \
  --dhcp-host=08:00:27:3D:80:E4,192.168.0.4,worker

# setup coredns
sudo -u vagrant mkdir -p /home/vagrant/coredns

sudo -u vagrant cat <<EOF | tee /home/vagrant/coredns/db.${CLUSTER_DOMAIN}
\$ORIGIN ${CLUSTER_DOMAIN}.
\$TTL 10800      ; 3 hours
@       3600 IN SOA sns.dns.icann.org. noc.dns.icann.org. (
                                2019010101 ; serial
                                7200       ; refresh (2 hours)
                                3600       ; retry (1 hour)
                                1209600    ; expire (2 weeks)
                                3600       ; minimum (1 hour)
                                )

_etcd-server-ssl._tcp.${CLUSTER_NAME}.${CLUSTER_DOMAIN}. 8640 IN    SRV 0 10 2380 etcd-0.${CLUSTER_NAME}.${CLUSTER_DOMAIN}.

api.${CLUSTER_NAME}.${CLUSTER_DOMAIN}.                        A ${VIP_IP}
api-int.${CLUSTER_NAME}.${CLUSTER_DOMAIN}.                    A ${VIP_IP}
${CLUSTER_NAME}-master-0.${CLUSTER_DOMAIN}.                   A ${MASTER_IP}
${CLUSTER_NAME}-worker-0.${CLUSTER_DOMAIN}.                   A ${WORKER_IP}
${CLUSTER_NAME}-bootstrap.${CLUSTER_DOMAIN}.                  A ${BOOTSTRAP_IP}
etcd-0.${CLUSTER_NAME}.${CLUSTER_DOMAIN}.                     IN  CNAME ${CLUSTER_NAME}-master-0.${CLUSTER_DOMAIN}.

\$ORIGIN apps.${CLUSTER_NAME}.${CLUSTER_DOMAIN}.
*                                                    A                ${VIP_IP}
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
nameserver 10.0.2.3
EOF

# none: NetworkManager will not modify resolv.conf. 
sudo sed -i "s|#plugins=ifcfg-rh,ibft|#plugins=ifcfg-rh,ibft\ndns=none|g" /etc/NetworkManager/NetworkManager.conf
sudo systemctl restart NetworkManager

# run coredns
sudo podman run -d --rm --name coredns \
  -d \
  -p 53:53 \
  -p 53:53/udp \
  -v /home/vagrant/coredns:/etc/coredns:z \
  coredns/coredns:latest \
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
 platform:
   none: {}
 pullSecret: '${PULL_SECRET}'
 sshKey: |
   ${SSH_KEY}
EOF

# download and setup openshift-install
sudo -u vagrant wget -v https://mirror.openshift.com/pub/openshift-v4/clients/ocp/4.1.0/openshift-install-linux-4.1.0.tar.gz
sudo -u vagrant tar xzf openshift-install-linux-4.1.0.tar.gz
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
sudo -u vagrant git clone https://github.com/madorn/upi-rt
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
pxe_os_image_url = "http://192.168.0.254:8080/assets/rhcos-4.1.0-x86_64-metal-bios.raw.gz"

bootstrap_public_ipv4 = "${BOOTSTRAP_IP}"
bootstrap_ign_file = "/tmp/baremetal/bootstrap.ign"
bootstrap_ipmi_host = "${BOOTSTRAP_IP}"
bootstrap_ipmi_user = "admin"
bootstrap_ipmi_pass = "admin"
bootstrap_mac_address = "${BOOTSTRAP_MAC}"

master_public_ipv4 = "${MASTER_IP}"
master_ign_file = "/tmp/baremetal/master.ign"
master_ipmi_host = "${MASTER_IP}"
master_ipmi_user = "admin"
master_ipmi_pass = "admin"
master_mac_address = "${MASTER_MAC}"
master_count = "1"
EOF

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
pxe_os_image_url = "http://192.168.0.254:8080/assets/rhcos-4.1.0-x86_64-metal-bios.raw.gz"

worker_public_ipv4 = "${WORKER_IP}"
worker_ign_file = "/tmp/baremetal/worker.ign"
worker_ipmi_host = "${WORKER_IP}"
worker_ipmi_user = "admin"
worker_ipmi_pass = "admin"
worker_mac_address = "${WORKER_MAC}"
worker_count = "1"
EOF

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
nameserver 192.168.0.254
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
