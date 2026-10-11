"""Trojan-insertion engine and ready-made Trojans.

  core   the engine: parse / render / extract_spec / apply_spec
  snip   the "snip" Trojan (split one net; SDA, SCL, MISO, MOSI, ...)
  swap   the "swap" Trojan (cross an RX/TX pair; UART, ...)
  cli    the command-line front end

The public API is re-exported from the top-level ``netlist_trojans`` package.
"""
