#!/usr/bin/env python

from ivn.vswitch import InfrasimvSwitchManager, start_process
from ivn.netns import InfrasimNamespaceManager
import sys
import os
import time
import shutil
import re

dhcp_service = "isc-dhcp-server"
dhcpd_config = "/etc/default/isc-dhcp-server"
dhcpd_config_bk = "/etc/default/isc-dhcp-server.bk"

if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            raise Exception(
                "Too few arguments, please specify <create/delete>")

        if sys.argv[1] == "create":
            vswitch_manager = InfrasimvSwitchManager(
                "./network_configuration.yml")
            vswitch_manager.create()
            rt, out, err = start_process(["service", dhcp_service, "stop"])
            if rt != 0:
                print rt, err
            shutil.move(dhcpd_config, dhcpd_config_bk)
            with open(dhcpd_config, "w+") as f:
                f.write("INTERFACES=\"br-int\"\n")

            rt, out, err = start_process(["service", dhcp_service, "start"])
            if rt != 0:
                raise Exception(err)
            time.sleep(3)
            inm = InfrasimNamespaceManager(
                "./network_configuration.yml", vswitch_manager.get_vswitch_int())
            inm.create()
        elif sys.argv[1] == "delete":
            rt, out, err = start_process(["service", dhcp_service, "stop"])
            if rt != 0:
                print rt, err
            vswitch_manager = InfrasimvSwitchManager(
                "./network_configuration.yml")
            vswitch_manager.delete()
            inm = InfrasimNamespaceManager(
                "./network_configuration.yml", vswitch_manager.get_vswitch_int())
            inm.delete()
            if os.path.exists(dhcpd_config) and os.path.exists(dhcpd_config_bk):
                shutil.move(dhcpd_config_bk, dhcpd_config)
            regex = r"(INTERFACES=)\"(.*)\"$"
            nic = None
            with open(dhcpd_config, "r+") as f:
                for line in f:
                    m = re.search(regex, line)
                    if m:
                        nic = m.group(2)
                        break
            print "You might need to check your original dhcpd nic {}" \
                  " and bring it up again.".format(nic)
        else:
            raise Exception("Command {} is not supported".format(sys.argv[1]))
    except Exception as e:
        print e
        sys.exit(1)
