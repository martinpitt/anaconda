#
# Copyright (C) 2020  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest

from pyanaconda.core.constants import SOURCE_TYPE_RPM_OSTREE
from pyanaconda.modules.payloads.constants import PayloadType
from pyanaconda.modules.payloads.payload.rpm_ostree.rpm_ostree import RPMOSTreeModule
from pyanaconda.modules.payloads.payload.rpm_ostree.rpm_ostree_interface import RPMOSTreeInterface
from pyanaconda.modules.payloads.payloads import PayloadsService
from pyanaconda.modules.payloads.payloads_interface import PayloadsInterface

from tests.nosetests.pyanaconda_tests.module_payload_shared import PayloadSharedTest, \
    PayloadKickstartSharedTest


class RPMOSTreeInterfaceTestCase(unittest.TestCase):
    """Test the RPM OSTree DBus module."""

    def setUp(self):
        self.module = RPMOSTreeModule()
        self.interface = RPMOSTreeInterface(self.module)

        self.shared_tests = PayloadSharedTest(
            test=self,
            payload=self.module,
            payload_intf=self.interface
        )

    def type_test(self):
        """Test the Type property."""
        self.shared_tests.check_type(PayloadType.RPM_OSTREE)

    def supported_sources_test(self):
        """Test the SupportedSourceTypes property."""
        self.assertEqual(self.interface.SupportedSourceTypes, [
            SOURCE_TYPE_RPM_OSTREE
        ])


class RPMOSTreeKickstartTestCase(unittest.TestCase):
    """Test the RPM OSTree kickstart commands."""

    def setUp(self):
        self.maxDiff = None
        self.module = PayloadsService()
        self.interface = PayloadsInterface(self.module)
        self.shared_ks_tests = PayloadKickstartSharedTest(
            test=self,
            payload_service=self.module,
            payload_service_intf=self.interface
        )

    def _check_properties(self, expected_source_type):
        payload = self.shared_ks_tests.get_payload()
        self.assertIsInstance(payload, RPMOSTreeModule)

        if expected_source_type is None:
            self.assertFalse(payload.sources)
        else:
            sources = payload.sources
            self.assertEqual(1, len(sources))
            self.assertEqual(sources[0].type.value, expected_source_type)

    def ostree_kickstart_test(self):
        ks_in = """
        ostreesetup --osname="fedora-atomic" --remote="fedora-atomic-28" --url="file:///ostree/repo" --ref="fedora/28/x86_64/atomic-host" --nogpg
        """
        ks_out = """
        # OSTree setup
        ostreesetup --osname="fedora-atomic" --remote="fedora-atomic-28" --url="file:///ostree/repo" --ref="fedora/28/x86_64/atomic-host" --nogpg
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_RPM_OSTREE)

    def priority_kickstart_test(self):
        ks_in = """
        ostreesetup --osname="fedora-iot" --url="https://compose/iot/" --ref="fedora/iot"
        url --url="https://compose/Everything"
        """
        ks_out = """
        # OSTree setup
        ostreesetup --osname="fedora-iot" --remote="fedora-iot" --url="https://compose/iot/" --ref="fedora/iot"
        """
        self.shared_ks_tests.check_kickstart(ks_in, ks_out)
        self._check_properties(SOURCE_TYPE_RPM_OSTREE)
