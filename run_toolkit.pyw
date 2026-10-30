# Windows: double-click this file to run the toolkit without a console window
# (.pyw files open with pythonw). All the code lives in run_toolkit.py.
import os
import runpy

runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_toolkit.py"),
               run_name="__main__")
