import subprocess
import yaml
import os


def start_process(args):
    try:
        p = subprocess.Popen(args,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()
        return (p.returncode, out, err)
    except OSError:
        return (-1, None, None)


class InfrasimvSwitchManager(object):
    def __init__(self, configuration):
        self.__vswitch_info = None
        self.__vswitch_int = None
        self.__vswitch_ex = None
        with open(configuration, "r") as fp:
            self.__vswitch_info = yaml.load(fp)

    def create(self):
        self.__vswitch_int = InfrasimvSwitch(self.__vswitch_info["switches"]["br-int"])
        self.__vswitch_ex = InfrasimvSwitch(self.__vswitch_info["switches"]["br-ex"])

        try:
            self.__vswitch_int.add_vswitch()
            self.__vswitch_ex.add_vswitch()
        except Exception as e:
            print e.message
            return

        # jxw, comment out the patch
        #self.__vswitch_ex.set_interface("phy-br-ex", "int-br-ex")
        #self.__vswitch_int.set_interface("int-br-ex", "phy-br-ex")

        self.__vswitch_ex.build_one_vswitch()
        self.__vswitch_int.build_one_vswitch()

    def delete(self):
        self.__vswitch_int = InfrasimvSwitch(self.__vswitch_info["switches"]["br-int"])
        self.__vswitch_ex = InfrasimvSwitch(self.__vswitch_info["switches"]["br-ex"])
        self.__vswitch_int.del_vswitch()
        self.__vswitch_ex.del_vswitch()

    def get_vswitch_int(self):
        return self.__vswitch_int


class InfrasimvSwitch(object):
    def __init__(self, vswitch_info):
        self.__vswitch_info = vswitch_info
        self.name = vswitch_info["ifname"]
        self.oif = None

    @staticmethod
    def get_vswitchs_list():
        return start_process(["ovs-vsctl", "show"])[1]

    def build_one_vswitch(self):
        # add port in configuration to vswitch
        if "ports" in self.__vswitch_info:
            for port in self.__vswitch_info["ports"]:
                self.add_port(port["ifname"])

        content = ""
        if self.__vswitch_info["type"] == "static":
            content += "auto {}\n".format(self.name)
            content += "iface {} inet static\n".format(self.name)
            for key, val in self.__vswitch_info.items():
                if key == "ifname" or key == "type" or key == "ports":
                    continue
                elif val:
                    content += "\t{} {}\n".format(key, val)
        elif self.__vswitch_info["type"] == "dhcp":
            content += "auto {}\n".format(self.name)
            content += "iface {} inet dhcp\n".format(self.name)
        else:
            raise Exception("Unsupported method {}.".format(self.__vswitch_info["type"]))

        with open("/etc/network/interfaces.d/{}".format(self.name), "w") as f:
            f.write(content)

        start_process(["ifdown", self.name])
        returncode, out, err = start_process(["ifup", self.name])
        if returncode != 0:
            raise Exception("Failed to if up {}\nError: ".format(self.name, err))

    def check_vswitch_exists(self):
        ret = start_process(["ovs-vsctl", "br-exists", self.name])[0]
        return ret == 0

    def add_vswitch(self):
        if self.check_vswitch_exists():
            print "vswitch {} already exists so not add it.".format(self.name)
            return

        if start_process(["ovs-vsctl", "add-br", self.name])[0] != 0:
            raise Exception("fail to create vswitch {}.".format(self.name))
        print "vswitch {} is created.".format(self.name)

    def del_vswitch(self):
        if not self.check_vswitch_exists():
            print "vswitch {} doesn't exist so not delete it".format(self.name)
        else:
            if start_process(["ovs-vsctl", "del-br", self.name])[0]:
                raise Exception("fail to delete vswitch {}".format(self.name))
            os.remove("/etc/network/interfaces.d/{}".format(self.name))
            print "vswitch {} is destroyed.".format(self.name)

    def add_port(self, ifname):
        if not self.check_vswitch_exists():
            raise Exception("vswitch {} doesn't exist, please add it first.".format(self.name))

        ret, output, outerr = start_process(["ovs-vsctl", "add-port", self.name, ifname])
        if ret != 0:
            print outerr

    def del_port(self, ifname):
        ret, output, outerr = start_process(["ovs-vsctl", "del-port", self.name, ifname])
        if ret != 0:
            print outerr

    def set_interface(self, ifname, peername):
        self.add_port(ifname)
        ret, output, outerr = start_process(["ovs-vsctl", "set", "interface", ifname, "type=patch", "options:peer={}".format(peername)])
        if ret != 0:
            raise Exception("fail to set interface {} for vswitch {}.".format(ifname, self.name))
