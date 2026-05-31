"""
Initialise kicad-cli such that it has a symbolic link to `<project directory>/kicad-cli`

Prerequisites: 
- Ensure that in .env file, the variable KICAD_CLI_PATH is set to the actual location that `kicad-cli` is installed at.

"""

import os
import subprocess
import time
import glob
import kicad_netlist_processer
import file_helpers
from skidl.netlist_to_skidl import legalize_name, NetSexp, PartSexp
from pathlib import Path
import json


class KiCadInterface:
    def __init__(self):
        self.KICAD_CLI_EXECUTABLE = os.getcwd()+"/kicad-cli"
        self._initialise_kicad_cli()

    def _initialise_kicad_cli(self):
        kicad_cli_path = Path(os.getenv("KICAD_CLI_PATH"))
        subprocess.run(["ln", "-s", kicad_cli_path, "kicad-cli"])

        print("Check if kicad-cli now works...")
        subprocess.run([self.KICAD_CLI_EXECUTABLE, "-h"])

    def export_netlist_with_kicad_cli(self, project_name: str, output_file_name: str):
        """
        Function to export .kicad_sch or .pro files to .net files using kicad-cli, so other Python scripts can use the resultant .net files.
        """
        print(f"Project schematic name: {project_name}")
        project_schematic_path = Path(project_name)
        if project_schematic_path.exists(): 
            print("Project exists! Creating netlist output at: ", output_file_name)
            subprocess.run([self.KICAD_CLI_EXECUTABLE, "sch", "export", "netlist", "--format", "kicadsexpr", project_schematic_path, "--output", output_file_name])
        else:
            raise Exception("No valid schematic")
    
    def export_spice_with_kicad_cli(self, project_name: str, output_file_name: str):
        """
        Function to export .kicad_sch or .pro files to .cir files using kicad-cli, so other Python scripts can use the resultant .cir files.
        """
        print(f"Project schematic name: {project_name}")
        project_schematic_path = Path(project_name)
        if project_schematic_path.exists(): 
            print("Project exists! Creating SPICE output at: ", output_file_name)
            subprocess.run([self.KICAD_CLI_EXECUTABLE, "sch", "export", "netlist", "--format", "spice", project_schematic_path, "--output", output_file_name])
        else:
            raise Exception("No valid schematic/project.")
    