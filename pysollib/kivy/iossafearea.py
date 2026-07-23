import ctypes
import logging

from kivy.utils import platform


class UIEdgeInsets(ctypes.Structure):
    _fields_ = [
        ('top', ctypes.c_double),
        ('left', ctypes.c_double),
        ('bottom', ctypes.c_double),
        ('right', ctypes.c_double),
    ]


class IosSafeArea:

    def __init__(self):
        self.top = 0
        self.bottom = 0
        if platform != 'ios':
            return
        try:
            from pyobjus import autoclass
            from pyobjus.objc_py_types import Factory
            Factory.registry['UIEdgeInsets'] = UIEdgeInsets
            shared = autoclass('UIApplication').sharedApplication()
            window = shared.keyWindow
            if window is None:
                windows = shared.windows
                if windows is not None and windows.count() > 0:
                    window = windows.objectAtIndex_(0)
            if window is None:
                return
            insets = window.safeAreaInsets()
            self.top = float(insets.top)
            self.bottom = float(insets.bottom)
            logging.info('IosSafeArea: top=%s bottom=%s', self.top, self.bottom)
        except Exception:
            logging.exception('IosSafeArea: failed to read safeAreaInsets')
