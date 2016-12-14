#!/usr/bin/env python

from ivn.vswitch import InfrasimvSwitchManager
from ivn.netns import InfrasimNamespaceManager
import sys


if __name__ == "__main__":
    if sys.argv[1] == "create":
        vswitch_manager = InfrasimvSwitchManager("./network_configuration.yml")
        vswitch_manager.create()
        inm = InfrasimNamespaceManager("./network_configuration.yml", vswitch_manager.get_vswitch_int())
        inm.create()
    elif sys.argv[1] == "delete":
        vswitch_manager = InfrasimvSwitchManager("./network_configuration.yml")
        vswitch_manager.delete()
        inm = InfrasimNamespaceManager("./network_configuration.yml", vswitch_manager.get_vswitch_int())
        inm.delete()
    else:
        print sys.argv[1]
