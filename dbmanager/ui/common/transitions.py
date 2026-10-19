"""
Window Transitions Module
Provides smooth animations for window transitions.
"""

from PyQt6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation


class WindowTransition:
    """Utility class for smooth window transitions."""

    @staticmethod
    def fade_in(window, duration=350, callback=None):
        """Fade in a window smoothly."""
        window.setWindowOpacity(0.0)
        window.show()
        window.raise_()
        window.activateWindow()

        anim = QPropertyAnimation(window, b"windowOpacity")
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        if callback:
            anim.finished.connect(callback)

        window._fade_anim = anim
        anim.start()
        return anim

    @staticmethod
    def fade_out(window, duration=300, callback=None):
        """Fade out a window smoothly."""
        anim = QPropertyAnimation(window, b"windowOpacity")
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)

        def on_finish():
            window.hide()
            window.setWindowOpacity(1.0)
            if callback:
                callback()

        anim.finished.connect(on_finish)
        window._fade_anim = anim
        anim.start()
        return anim

    @staticmethod
    def cross_fade(from_window, to_window, duration=400, callback=None):
        """Cross-fade between two windows."""
        to_window.setWindowOpacity(0.0)
        to_window.show()
        to_window.raise_()

        fade_out = QPropertyAnimation(from_window, b"windowOpacity")
        fade_out.setDuration(duration)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InOutCubic)

        fade_in = QPropertyAnimation(to_window, b"windowOpacity")
        fade_in.setDuration(duration)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.InOutCubic)

        group = QParallelAnimationGroup()
        group.addAnimation(fade_out)
        group.addAnimation(fade_in)

        def on_finish():
            from_window.hide()
            from_window.setWindowOpacity(1.0)
            to_window.activateWindow()
            if callback:
                callback()

        group.finished.connect(on_finish)

        from_window._cross_fade_group = group
        to_window._cross_fade_group = group
        group.start()
        return group

