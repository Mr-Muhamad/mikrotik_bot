"""Registration parts package.

Split from ``bot/registrations.py`` to keep the registration catalog
organised by domain while preserving the exact import/execution order
required by ``test_registration_order.py``.

Import order contract:
    bot.registrations imports ``standalone`` before ``conversation`` so that
    standalone decorators execute before conversation (entry_points/states/
    fallbacks) decorators. The final ``build_all`` in ``bot.registrations``
    is unchanged and still registers separate CHs before ``build_application``.
"""
