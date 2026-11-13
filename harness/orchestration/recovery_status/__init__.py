"""The parts of the shared recovery status and action API; ``recovery_api`` re-exports them.

* ``model``: the registry vocabulary, the diagnostics and the check results;
* ``runtime``: whether the runtime hello keeps the recovery records;
* ``intent``: the durable intent every action except ``skip`` records;
* ``survey``: the read-only reconciliation checks of one batch and the ``recoveryStatus.v1``
  document, composed of ``inputs``, ``batch_state``, ``evidence`` and ``dispatches``;
* ``actions``: ``status``, ``reload``, ``fix``, ``skip`` and ``abort``;
* ``resume``: the action that releases the hold and reacts to the observed executions.
"""
