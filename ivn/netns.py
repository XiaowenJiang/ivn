import os
from pyroute2 import IPDB
from pyroute2 import netns
from pyroute2.iproute import IPRoute
import yaml
import netifaces
from .vswitch import start_process

interface_index = 0


class InfrasimNamespaceManager(object):
    def __init__(self, configuration, vswitch_instance):
        self.__ns_info = None
        self.__vswitch = vswitch_instance
        with open(configuration, "r") as f:
            self.__ns_info = yaml.load(f)
        self.__ns_list = []

    def create(self):
        if self.__vswitch is None:
            raise Exception("br-int should be created prior to creating namespace")

        for ns in self.__ns_info["namespaces"]:
            ns_obj = InfrasimNamespace(self.__vswitch, ns)
            self.__ns_list.append(ns_obj)
        self.build_topology()
        self.build_configuration()
        self.link_up_all()
        print "namespaces specified in configuration are created."

    def delete(self):
        for ns in self.__ns_info["namespaces"]:
            ns_obj = InfrasimNamespace(self.__vswitch, ns)
            ns_obj.del_namespace()
        self.link_delete_all()

    def build_topology(self):
        for ns_obj in self.__ns_list:
            ns_obj.build_one_namespace()

    def build_configuration(self):
        for ns_obj in self.__ns_list:
            ns_obj.build_ns_configuration()

    def link_up_all(self):
        for ns_obj in self.__ns_list:
            ns_obj.link_up_all()

    def link_delete_all(self):
        for interface in netifaces.interfaces():
            if str(interface).startswith("veth"):
                start_process(["ip", "link", "delete", interface])


class Interface(object):
    def __init__(self, interface_info):
        self.__intf_info = interface_info

    def handle_dhcp_type(self):
        content = ""
        content += "auto {}\n".format(self.__intf_info["ifname"])
        content += "iface {} inet dhcp\n".format(self.__intf_info["ifname"])
        content += "\n"
        return content

    def handle_static_type(self):
        content = ""
        content += "auto {}\n".format(self.__intf_info["ifname"])
        content += "iface {} inet static\n".format(self.__intf_info["ifname"])
        content += self.handle_body()
        content += "\n"
        return content

    def handle_body(self):
        content = ""
        sub_content = ""
        for key, val in self.__intf_info.items():
            if key == "ifname" or key == "type" or val is None:
                continue

            if key == "pair":
                continue

            elif key == "bridge":
                sub_content = ""
                old_intf_info = self.__intf_info
                self.__intf_info = self.__intf_info['bridge']
                sub_content = self.compose()
                self.__intf_info = old_intf_info
            else:
                content += "\t{} {}\n".format(key, val)

        content += "\n"
        content += sub_content
        return content

    def compose(self):
        if self.__intf_info["type"] == "dhcp":
            return self.handle_dhcp_type()
        elif self.__intf_info["type"] == "static":
            return self.handle_static_type()
        else:
            raise Exception("Unsupported method {}.".format(self.__intf_info["type"]))


class InfrasimNamespace(object):
    def __init__(self, vswitch_instance, ns_info):
        self.__ns_info = ns_info
        self.name = ns_info['name']
        self.ip = IPRoute()
        # self.ipdb = IPDB(nl=NetNS(self.name))
        self.main_ipdb = IPDB()
        self.__vswitch = vswitch_instance

    @staticmethod
    def get_namespaces_list():
        return netns.listnetns()

    def build_one_namespace(self):
        self._create_namespace()

        for intf in self.__ns_info["interfaces"]:
            # get name
            ifname = intf["ifname"]
            if intf.get("pair") is False:
                self.create_single_virtual_intf_in_ns(intf)
            else:
                global interface_index
                self.create_ip_link_in_ns(ifname, "veth{}".format(interface_index))
                if 'bridge' in intf:
                    self.create_bridge(intf=ifname, br_name=intf['bridge']['ifname'])
                self.__vswitch.add_port("veth{}".format(interface_index))
                idx = self.ip.link_lookup(ifname="veth{}".format(interface_index))[0]
                self.ip.link("set", index=idx, state="up")
                interface_index += 1

    def _create_namespace(self):
        if self.name in self.get_namespaces_list():
            print "name space {} exists.".format(self.name)
            return
        netns.create(self.name)

    def del_namespace(self):
        if self.name in netns.listnetns():
            netns.remove(self.name)

    def create_single_virtual_intf_in_ns(self, intf):
        ifname = intf['ifname']
        if len(self.ip.link_lookup(ifname=ifname)) > 0:
            print "ip link {} exists so not create it.".format(ifname)
            return

        self.main_ipdb.create(ifname=ifname, kind="dummy").commit()
        with self.main_ipdb.interfaces[ifname] as veth:
            veth.net_ns_fd = self.name

        if 'bridge' in intf:
            self.create_bridge(intf=ifname, br_name=intf['bridge']['ifname'])

    def create_ip_link_in_ns(self, ifname, peername):
        if len(self.ip.link_lookup(ifname=ifname)) > 0:
            print "ip link {} exists so not create it.".format(ifname)
            return

        if len(self.ip.link_lookup(ifname=peername)) > 0:
            print "ip link {} exists so not create it.".format(peername)
            return

        # create link peer
        self.main_ipdb.create(ifname=ifname, kind="veth", peer=peername).commit()
        with self.main_ipdb.interfaces[ifname] as veth:
            veth.net_ns_fd = self.name

    def exec_cmd_in_namespace(self, cmd):
        start_process(["ip", "netns", "exec", self.name] + cmd)

    def link_up_all(self):
        # setup lo
        # self.exec_cmd_in_namespace(["ifdown", "lo"])
        # self.exec_cmd_in_namespace(["ifup", "lo"])
        self.exec_cmd_in_namespace(["ip", "link", "set", "dev", "lo", "up"])

        for intf_info in self.__ns_info["interfaces"]:
            if "bridge" in intf_info:
                self.exec_cmd_in_namespace(["ip", "link", "set", "dev", intf_info["ifname"], "up"])
                self.exec_cmd_in_namespace(["ifdown", intf_info["bridge"]["ifname"]])
                self.exec_cmd_in_namespace(["ifup", intf_info["bridge"]["ifname"]])
            else:
                self.exec_cmd_in_namespace(["ifdown", intf_info["ifname"]])
                self.exec_cmd_in_namespace(["ifup", intf_info["ifname"]])

    def create_bridge(self, intf="einf0", br_name="br0"):
        self.exec_cmd_in_namespace(["brctl", "addbr", "{}".format(br_name)])
        self.exec_cmd_in_namespace(["brctl", "addif", "{}".format(br_name), intf])
        self.exec_cmd_in_namespace(["brctl", "setfd", "{}".format(br_name), "0"])
        self.exec_cmd_in_namespace(["brctl", "sethello", "{}".format(br_name), "1"])
        self.exec_cmd_in_namespace(["brctl", "stp", "{}".format(br_name), "no"])
        self.exec_cmd_in_namespace(["ifconfig", intf, "promisc"])

    def build_ns_configuration(self):
        netns_path = "/etc/netns"
        ns_network_dir = os.path.join(netns_path, self.name, "network")

        if_down_dir = os.path.join(ns_network_dir, "if-down.d")
        if not os.path.exists(if_down_dir):
            os.makedirs(if_down_dir)

        if_post_down_dir = os.path.join(ns_network_dir, "if-post-down.d")
        if not os.path.exists(if_post_down_dir):
            os.makedirs(if_post_down_dir)

        if_pre_up_dir = os.path.join(ns_network_dir, "if-pre-up.d")
        if not os.path.exists(if_pre_up_dir):
            os.makedirs(if_pre_up_dir)

        if_up_dir = os.path.join(ns_network_dir, "if-up.d")
        if not os.path.exists(if_up_dir):
            os.makedirs(if_up_dir)

        content = ""
        content += "auto lo\n"
        content += "iface lo inet loopback\n"
        content += "\n"

        intf_list = []
        for intf_info in self.__ns_info["interfaces"]:
            intf_obj = Interface(intf_info)
            intf_list.append(intf_obj)

        for iobj in intf_list:
            content += iobj.compose()

        with open(os.path.join(ns_network_dir, "interfaces"), "w") as f:
            f.write(content)
