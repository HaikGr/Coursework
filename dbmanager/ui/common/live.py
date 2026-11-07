"""Texts and styles that follow the language and the theme without the window being made again.

bind(setter, source) calls the setter now, and again whenever the language or the theme changes, for as long
as the object it belongs to lives. source is a catalogue key, with its placeholders as keyword arguments,
or a function that returns the value:

    bind(label.setText, "auth.sign_in.heading")
    bind(button.setToolTip, "dashboard.top_bar.account_tip", username=name)
    bind(self.count_label.setText, lambda: trn("<area>.<rows>", count))
    bind(partial(combo.setItemText, 0), "<area>.<first_choice>")
    bind(table.setHorizontalHeaderLabels, lambda: [tr("<area>.<name>"), tr("<area>.<type>")])
    bind(partial(tree_item.setText, 0), "<area>.<label>")      # items of trees and tables too

Binding the same setter again replaces what it showed, so code that refreshes a text binds it each time.
theme.style(widget, template) binds a widget's style sheet the same way.

A modal dialog made for one exec() can use plain tr() and theme.qss(): nothing can change while it is open.

The bindings are kept on the objects themselves, so they go with them; this module holds the objects weakly,
by identity (a QTreeWidgetItem cannot be hashed).
"""

import weakref
from functools import partial

from PyQt6 import sip

from dbmanager.i18n import tr

_ATTRIBUTE = "_live_bindings"
_owners = {}  # id(owner) -> weak reference to it, gone with it


def bind(setter, source, /, **params):
    """Call setter with source's value now and on every change of language or theme (see the module)."""
    args = ()
    if isinstance(setter, partial):
        args, setter = setter.args, setter.func
    owner = getattr(setter, "__self__", None)
    if owner is None:
        raise TypeError("bind() takes a bound method of a widget, such as label.setText")
    if callable(source):
        if params:
            raise TypeError("placeholders go into the function, not into bind()")
        produce = source
    else:
        produce = partial(tr, source, **params)

    name = setter.__name__
    bindings = getattr(owner, _ATTRIBUTE, None)
    if bindings is None:
        bindings = {}
        setattr(owner, _ATTRIBUTE, bindings)
    bindings[(name, args)] = produce
    key = id(owner)
    if key not in _owners:
        _owners[key] = weakref.ref(owner, lambda _, key=key: _owners.pop(key, None))
    setter(*args, produce())


def unbind(setter):
    """Stop following changes (the text set last stays)."""
    args = ()
    if isinstance(setter, partial):
        args, setter = setter.args, setter.func
    bindings = getattr(getattr(setter, "__self__", None), _ATTRIBUTE, None)
    if bindings:
        bindings.pop((setter.__name__, args), None)


def refresh():
    """Set every bound value again, after the language or the theme changed."""
    for key, reference in list(_owners.items()):
        owner = reference()
        if owner is None or (isinstance(owner, sip.simplewrapper) and sip.isdeleted(owner)):
            _owners.pop(key, None)
            continue
        for (name, args), produce in list(getattr(owner, _ATTRIBUTE, {}).items()):
            try:
                getattr(owner, name)(*args, produce())
            except RuntimeError as error:
                if "has been deleted" not in str(error):
                    raise
                # Something the value was made from is gone (its widget was deleted): it is not shown either
                getattr(owner, _ATTRIBUTE, {}).pop((name, args), None)
