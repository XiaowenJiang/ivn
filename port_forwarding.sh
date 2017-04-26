#!/usr/bin/env sh

src_ip=$1
src_port=$2
dest_port=$3

help() {
    echo "$0 <source ip> <source port> <target port>"
    echo "\nexample: ./port_forwarding 172.31.128.20 5901 15901"
    echo "then you can view VNC from <host ip>:15901\n"
    exit 1
}

[ -z $src_ip ]  && help
[ -z $src_port ]  && help
[ -z $dest_port ]  && help

preinit() {
    sysctl -w net.ipv4.ip_forward=1
    iptables -t nat -F PREROUTING
    iptables -t nat -F POSTROUTING
}

forward() {
    iptables -A PREROUTING -t nat -p tcp --dport $3 -j DNAT --to $1:$2
    iptables -t nat -A POSTROUTING  -d $1 -p tcp --dport $2 -j MASQUERADE
}

preinit

forward $src_ip $src_port $dest_port
