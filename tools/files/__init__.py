import importlib.util, os
_dir = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "_tools_files", os.path.join(_dir, "files.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
TOOLS = _mod.TOOLS
