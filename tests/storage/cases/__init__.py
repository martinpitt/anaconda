#!/usr/bin/python
#
# Copyright (C) 2013  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Chris Lumens <clumens@redhat.com>

import logging
import os, sys
import re

import blivet

blivet.util.set_up_logging()
blivet_log = logging.getLogger("blivet")
blivet_log.info(sys.argv[0])

from pyanaconda.installclass import DefaultInstall
from pyanaconda.kickstart import AnacondaKSHandler, AnacondaKSParser, doKickstartStorage
from pykickstart.errors import KickstartError

class FailedTest(Exception):
    def __init__(self, got, expected):
        Exception.__init__(self)
        self.got = got
        self.expected = expected

class TestCase(object):
    """A TestCase is a way of grouping related TestCaseComponent objects
       together into a single place.  It provides a way of iterating through
       all these components, running each, and tabulating the results.  If any
       component fails, the entire TestCase fails.

       Class attributes:

       components   -- A list of TestCaseComponent classes.
       desc         -- A description of what this test is supposed to be
                       testing.
       name         -- An identifying string given to this TestCase.
       platforms    -- A list of blivet.platform.Platform subclasses that this
                       TestCase is valid for.  This TestCase will only run on
                       matching platforms.  If the list is empty, it is assumed
                       to be valid for all platforms.
    """
    components  = []
    desc        = ""
    name        = ""
    platforms   = []

    def __init__(self):
        pass

    def run(self):
        """Iterate over all components, running each, and collecting the
           results.
        """
        successes = 0
        failures = 0

        if self.platforms and blivet.platform.getPlatform().__class__.__name__ not in self.platforms:
            print("Test %s skipped:  not valid for this platform" % self.name)
            return

        for c in self.components:
            obj = c()

            try:
                obj._run()
            except FailedTest as e:
                print("Test %s-%s failed:\n\tExpected: %s\n\tGot:      %s" % (self.name, obj.name, e.expected, e.got))
                failures += 1
                continue

            print("Test %s-%s succeeded" % (self.name, obj.name))
            successes += 1

        print("Test %s summary:" % self.name)
        print("\tSuccesses: %s" % successes)
        print("\tFailures:  %s" % failures)
        return failures

class TestCaseComponent(object):
    """A TestCaseComponent is one individual test that runs as part of a TestCase.
       It consists of a set of disk images provided by self.disksToCreate, a
       kickstart storage snippet provided by self.ks, and an expected error
       condition provided by self.expectedExceptionType and self.expectedExceptionText.
       If the TestCaseComponent is expected to succeed, these latter two should
       just be set to None.

       A TestCaseComponent succeeds in the following cases:

       * No exception is encountered, and self.expectedExceptionType is None.

       A TestCaseComponent fails in all other cases.

       Class attributes:

       name -- An identifying string given to this TestCaseComponent.
    """
    name = ""

    def __init__(self):
        """Create a new TestCaseComponent instance.  This __init__ method should
           typically do very little.  However, subclasses must be sure to set
           self.disksToCreate.  This attribute is a list of (disk name, blivet.Size)
           tuples that will be used in this test.  Disks given in this list will
           be automatically created by setupDisks and destroyed by tearDownDisks.
        """
        self._disks     = {}
        self._blivet    = None

        self.disksToCreate = []

    @property
    def ks(self):
        """Return the storage-specific portion of a kickstart file used for
           performing this test.  The kickstart snippet must be provided as
           text.  Only storage commands will be tested.  No bootloader actions
           will be performed.
        """
        return ""

    def setupDisks(self):
        """Create all disk images given by self.disksToCreate and initialize
           the storage module.  Subclasses may override this method, but they
           should be sure to call the base method as well.
        """
        self._blivet = blivet.Blivet()

        # blivet only sets up the bootloader in installer_mode.  We don't
        # want installer_mode, though, because that involves running lots
        # of programs on the host and setting up all sorts of other things.
        # Thus, we set it up manually.
        from pyanaconda.bootloader import get_bootloader
        self._blivet._bootloader = get_bootloader()

        for (name, size) in self.disksToCreate:
            self._disks[name] = blivet.util.create_sparse_tempfile(name, size)
            self._blivet.config.diskImages[name] = self._disks[name]

        self._blivet.reset()

    def tearDownDisks(self):
        """Disable any disk images used by this test component and remove their
           image files from the host system.  Subclasses may override this
           method, but they should call the base method as well to make sure
           the images get destroyed.
        """
        # pylint: disable=undefined-variable
        self._blivet.devicetree.teardownDiskImages()

        for d in self._disks.values():
            os.unlink(d)

    @property
    def expectedExceptionType(self):
        """Should this test component be expected to fail, this property returns
           the exception type.  If this component is not expected to fail, this
           property returns None.  All components that are expected to fail
           should override this property.
        """
        return None

    @property
    def expectedExceptionText(self):
        """Should this test component be expected to fail, this property returns
           a regular expression that the raised exception's text must match.
           Otherwise, this property returns None.  All components that are
           expected to fail should override this property.
        """
        return None

    def _text_matches(self, s):
        prog = re.compile(self.expectedExceptionText)

        for line in s.splitlines():
            match = prog.match(line)
            if match:
                return match

        return None

    def _run(self):
        from blivet.errors import StorageError

        # Set up disks/blivet.
        try:
            self.setupDisks()

            # Parse the kickstart using anaconda's parser, since it has more
            # advanced error detection.  This also requires having storage set
            # up first.
            parser = AnacondaKSParser(AnacondaKSHandler())
            parser.readKickstartFromString(self.ks)

            instClass = DefaultInstall()

            doKickstartStorage(self._blivet, parser.handler, instClass)
            self._blivet.updateKSData()
            self._blivet.doIt()
        except (KickstartError, StorageError) as e:
            # anaconda handles expected kickstart errors (like parsing busted
            # input files) by printing the error and quitting.  For testing, an
            # error might be expected so we should compare the result here with
            # what is expected.
            if self.expectedExceptionType and isinstance(e, self.expectedExceptionType):
                # We expected an exception, and we got one of the correct type.
                # If it also contains the string we were expecting, then the
                # test case passes.  Otherwise, it's a failure.
                if self.expectedExceptionText and self._text_matches(str(e)):
                    return
                else:
                    raise FailedTest(str(e), self.expectedExceptionText)
            else:
                # We either got an exception when we were not expecting one,
                # or we got one of a type other than what we were expecting.
                # Either of these cases indicates a failure of the test case.
                raise FailedTest(e, self.expectedExceptionType)
        finally:
            self.tearDownDisks()

        if self.expectedExceptionType:
            raise FailedTest(None, self.expectedExceptionType)

        return