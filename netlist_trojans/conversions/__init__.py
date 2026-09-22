"""Converters that consume infected netlists produced by ``netlist_trojans``.

- ``convert_circuits``: infected ``.net`` -> hierarchical circuit JSON (needs pcb_qa)
- ``convert_spice``: infected ``.net`` -> infected SPICE ``.cir`` (needs pcb_qa's
  Clean ``.cir`` templates)
- ``run_spice``: batch-run ``ngspice`` over generated ``.cir`` files
"""
