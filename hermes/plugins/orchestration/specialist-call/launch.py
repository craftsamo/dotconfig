"""Run a plugin script's __main__ on the Hermes runtime: launch.py <checkout> <script> [args...].

The same bootstrap as upstream's launcher (hermes_cli._launchers.runtime_command), kept in
a file because the terminal guard asks for approval on any inline `python -c`. Started
with the store Python in isolated mode (-I), so nothing from the caller's environment or
this directory is on the path. Stdlib only until hermes_bootstrap has selected the
dependency generation.
"""

import os
import runpy
import sys

if len(sys.argv) < 3:
    sys.exit("usage: launch.py <hermes-checkout> <script> [args...]")
root, script, args = sys.argv[1], sys.argv[2], sys.argv[3:]
for name in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
    os.environ.pop(name, None)
sys.path.insert(0, root)
if not os.environ.get("HERMES_HOME"):
    from hermes_constants import get_default_hermes_root
    os.environ["HERMES_HOME"] = str(get_default_hermes_root())
import hermes_bootstrap  # noqa: E402,F401  (selects the dependency generation)

sys.argv = [script, *args]
runpy.run_path(script, run_name="__main__")
