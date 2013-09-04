# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
#
# Autopilot Functional Test Tool
# Copyright (C) 2012-2013 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


import json
import os
from tempfile import mktemp
from testtools import TestCase, skipIf
from testtools.matchers import IsInstance, Equals, raises
from textwrap import dedent
from unittest import SkipTest
from mock import patch

from autopilot import platform
from autopilot.testcase import AutopilotTestCase, multiply_scenarios
from autopilot.input import Keyboard, Mouse, Pointer, Touch
from autopilot.input._common import get_center_point
from autopilot.matchers import Eventually
from autopilot.utilities import on_test_started


class InputStackKeyboardBase(AutopilotTestCase):

    scenarios = [
        ('X11', dict(backend='X11')),
        ('UInput', dict(backend='UInput')),
    ]

    def setUp(self):
        super(InputStackKeyboardBase, self).setUp()
        if self.backend == 'UInput' and not (
                os.access('/dev/autopilot-uinput', os.W_OK) or
                os.access('/dev/uinput', os.W_OK)):
            raise SkipTest(
                "UInput backend currently requires write access to "
                "/dev/autopilot-uinput or /dev/uinput")


class InputStackKeyboardCreationTests(InputStackKeyboardBase):

    def test_can_create_backend(self):
        keyboard = Keyboard.create(self.backend)
        self.assertThat(keyboard, IsInstance(Keyboard))


class InputStackKeyboardTypingTests(InputStackKeyboardBase):

    scenarios = multiply_scenarios(
        InputStackKeyboardBase.scenarios,
        [
            ('lower_alpha', dict(input='abcdefghijklmnopqrstuvwxyz')),
            ('upper_alpha', dict(input='ABCDEFGHIJKLMNOPQRSTUVWXYZ')),
            ('numeric', dict(input='0123456789')),
            ('punctuation', dict(input='`~!@#$%^&*()_-+={}[]|\\:;"\'<>,.?/')),
            ('whitespace', dict(input='\t\n'))
        ]
    )

    def start_mock_app(self):
        window_spec_file = mktemp(suffix='.json')
        window_spec = {"Contents": "TextEdit"}
        json.dump(
            window_spec,
            open(window_spec_file, 'w')
        )
        self.addCleanup(os.remove, window_spec_file)

        return self.launch_test_application('window-mocker', window_spec_file)

    def pick_app_launcher(self, app_path):
        # force Qt app introspection:
        from autopilot.introspection.qt import QtApplicationLauncher
        return QtApplicationLauncher()

    def test_text_typing(self):
        """Typing text must produce the correct characters in the target
        app.

        """
        app_proxy = self.start_mock_app()
        text_edit = app_proxy.select_single('QTextEdit')

        # make sure the text edit has keyboard focus:
        self.mouse.click_object(text_edit)

        # create keyboard and type the text.
        keyboard = Keyboard.create(self.backend)
        keyboard.type(self.input, 0.01)

        self.assertThat(text_edit.plainText,
                        Eventually(Equals(self.input)),
                        "app shows: " + text_edit.plainText
                        )

    def test_typing_with_contextmanager(self):
        """Typing text must produce the correct characters in the target
        app.

        """
        app_proxy = self.start_mock_app()
        text_edit = app_proxy.select_single('QTextEdit')

        keyboard = Keyboard.create(self.backend)
        with keyboard.focused_type(text_edit) as kb:
            kb.type(self.input, 0.01)

            self.assertThat(
                text_edit.plainText,
                Eventually(Equals(self.input)),
                "app shows: " + text_edit.plainText
            )

    def test_keyboard_keys_are_released(self):
        """Typing characters must not leave keys pressed."""
        app_proxy = self.start_mock_app()
        text_edit = app_proxy.select_single('QTextEdit')

        # make sure the text edit has keyboard focus:
        self.mouse.click_object(text_edit)
        keyboard = Keyboard.create(self.backend)

        for character in self.input:
            self.assertThat(self._get_pressed_keys_list(), Equals([]))
            keyboard.type(character, 0.01)
            self.assertThat(self._get_pressed_keys_list(), Equals([]))

    def _get_pressed_keys_list(self):
        """Get a list of keys pressed, but not released from the backend we're
        using.

        """
        if self.backend == 'X11':
            from autopilot.input._X11 import _PRESSED_KEYS
            return _PRESSED_KEYS
        elif self.backend == 'UInput':
            from autopilot.input._uinput import _PRESSED_KEYS
            return _PRESSED_KEYS
        else:
            self.fail("Don't know how to get pressed keys list for backend "
                      + self.backend
                      )


@skipIf(platform.model() == 'Desktop', "Only on device")
class OSKBackendTests(AutopilotTestCase):
    """Testing the Onscreen Keyboard (Ubuntu Keyboard) backend specifically.

    There are limitations (i.e. on device only, window-mocker doesn't work on
    the device, can't type all the characters that X11/UInput can.) that
    necessitate this split into it's own test class.

    """

    scenarios = [
        ('lower_alpha', dict(input='abcdefghijklmnopqrstuvwxyz')),
        ('upper_alpha', dict(input='ABCDEFGHIJKLMNOPQRSTUVWXYZ')),
        ('numeric', dict(input='0123456789')),
        ('punctuation', dict(input='`~!@#$%^&*()_-+={}[]|\\:;"\'<>,.?/')),
    ]

    def launch_test_input_area(self):
        self.app = self._launch_simple_input()
        text_area = self.app.select_single("QQuickTextInput")

        return text_area

    def _start_qml_script(self, script_contents):
        """Launch a qml script."""
        qml_path = mktemp(suffix='.qml')
        open(qml_path, 'w').write(script_contents)
        self.addCleanup(os.remove, qml_path)

        return self.launch_test_application(
            "qmlscene",
            qml_path,
            app_type='qt',
        )

    def _launch_simple_input(self):
        simple_script = dedent("""
        import QtQuick 2.0
        import Ubuntu.Components 0.1

        Rectangle {
            id: window
            objectName: "windowRectangle"
            color: "lightgrey"

            Text {
                id: inputLabel
                text: "OSK Tests"
                font.pixelSize: units.gu(3)
                anchors {
                    left: input.left
                    top: parent.top
                    topMargin: 25
                    bottomMargin: 25
                }
            }

            TextField {
                id: input;
                objectName: "input"
                anchors {
                    top: inputLabel.bottom
                    horizontalCenter: parent.horizontalCenter
                    topMargin: 10
                }
                inputMethodHints: Qt.ImhNoPredictiveText
            }
        }

        """)

        return self._start_qml_script(simple_script)

    def test_can_type_string(self):
        """Typing text must produce the expected characters in the input
        field.

        """

        text_area = self.launch_test_input_area()
        keyboard = Keyboard.create('OSK')
        pointer = Pointer(Touch.create())
        pointer.click_object(text_area)
        keyboard._keyboard.wait_for_keyboard_ready()

        keyboard.type(self.input)

        self.assertThat(text_area.text, Eventually(Equals(self.input)))

    def test_focused_typing_contextmanager(self):
        """Typing text using the 'focused_typing' context manager must not only
        produce the expected characters in the input field but also cleanup the
        OSK afterwards too.

        """
        text_area = self.launch_test_input_area()
        keyboard = Keyboard.create('OSK')
        with keyboard.focused_type(text_area) as kb:
            kb.type(self.input)
            self.assertThat(
                text_area.text,
                Eventually(Equals(self.input))
            )
        self.assertThat(
            keyboard._keyboard.is_available,
            Eventually(Equals(False))
        )


class MouseTestCase(AutopilotTestCase):

    def test_move_to_nonint_point(self):
        """Test mouse does not get stuck when we move to a non-integer point.

        LP bug #1195499.

        """
        device = Mouse.create()
        device.move(10, 10.6)
        self.assertEqual(device.position(), (10, 10))

    @patch('autopilot.platform.model', new=lambda *args: "Not Desktop", )
    def test_mouse_creation_on_device_raises_useful_error(self):
        """Trying to create a mouse device on the phablet devices must raise an
        explicit exception.

        """
        expected_exception = RuntimeError(
            "Cannot create a Mouse on the phablet devices."
        )
        self.assertThat(lambda: Mouse.create(),
                        raises(expected_exception))


class TouchTests(AutopilotTestCase):

    def setUp(self):
        super(TouchTests, self).setUp()
        self.device = Touch.create()

        self.app = self.start_mock_app()
        self.widget = self.app.select_single('MouseTestWidget')
        self.button_status = self.app.select_single(
            'QLabel', objectName='button_status')

    def start_mock_app(self):
        window_spec_file = mktemp(suffix='.json')
        window_spec = {"Contents": "MouseTest"}
        json.dump(
            window_spec,
            open(window_spec_file, 'w')
        )
        self.addCleanup(os.remove, window_spec_file)

        return self.launch_test_application(
            'window-mocker', window_spec_file, app_type='qt')

    def test_tap(self):
        x, y = get_center_point(self.widget)
        self.device.tap(x, y)

        self.assertThat(
            self.button_status.text, Eventually(Equals("Touch Release")))

    def test_press_and_release(self):
        x, y = get_center_point(self.widget)
        self.device.press(x, y)

        self.assertThat(
            self.button_status.text, Eventually(Equals("Touch Press")))

        self.device.release()
        self.assertThat(
            self.button_status.text, Eventually(Equals("Touch Release")))


class PointerWrapperTests(AutopilotTestCase):

    def test_can_move_touch_wrapper(self):
        device = Pointer(Touch.create())
        device.move(34, 56)

        self.assertThat(device._x, Equals(34))
        self.assertThat(device._y, Equals(56))

    def test_touch_drag_updates_coordinates(self):
        """The Pointer wrapper must update it's x and y properties when
        wrapping a touch object and performing a drag operation.

        """
        class FakeTouch(Touch):
            def __init__(self):
                pass

            def drag(self, x1, y1, x2, y2):
                pass

        p = Pointer(FakeTouch())
        p.drag(0, 0, 100, 123)
        self.assertThat(p.x, Equals(100))
        self.assertThat(p.y, Equals(123))


class InputStackCleanupTests(TestCase):

    def test_cleanup_called(self):
        """Derived classes cleanup method must be called when interface cleanup
        method is called.

        """

        class FakeKeyboard(Keyboard):

            cleanup_called = False

            @classmethod
            def on_test_end(cls, test_instance):
                FakeKeyboard.cleanup_called = True

        class FakeTestCase(TestCase):

            def test_foo(self):
                on_test_started(self)

                FakeKeyboard()

        FakeTestCase("test_foo").run()

        self.assertThat(FakeKeyboard.cleanup_called, Equals(True))


class InputStackCleanup(AutopilotTestCase):

    def test_keyboard_keys_released_X11(self):
        """Cleanup must release any keys that an X11 keyboard has had
        pressed."""
        class FakeTestCase(AutopilotTestCase):
            def test_press_key(self):
                kb = Keyboard.create('X11')
                kb.press('Shift')

        test_result = FakeTestCase("test_press_key").run()

        self.assertThat(test_result.wasSuccessful(), Equals(True))
        from autopilot.input._X11 import _PRESSED_KEYS
        self.assertThat(_PRESSED_KEYS, Equals([]))

    def test_keyboard_keys_released_UInput(self):
        """Cleanup must release any keys that an UInput keyboard has had
        pressed."""
        class FakeTestCase(AutopilotTestCase):
            def test_press_key(self):
                kb = Keyboard.create('UInput')
                kb.press('Shift')

        test_result = FakeTestCase("test_press_key").run()

        self.assertThat(test_result.wasSuccessful(), Equals(True))
        from autopilot.input._uinput import _PRESSED_KEYS
        self.assertThat(_PRESSED_KEYS, Equals([]))

    @patch('autopilot.input._X11.fake_input', new=lambda *args: None, )
    def test_mouse_button_released(self):
        """Cleanup must release any mouse buttons that have been pressed."""
        class FakeTestCase(AutopilotTestCase):
            def test_press_button(self):
                mouse = Mouse.create('X11')
                mouse.press()

        test_result = FakeTestCase("test_press_button").run()

        from autopilot.input._X11 import _PRESSED_MOUSE_BUTTONS
        self.assertThat(test_result.wasSuccessful(), Equals(True))
        self.assertThat(_PRESSED_MOUSE_BUTTONS, Equals([]))

