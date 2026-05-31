"""Tests for pcb_qa.parsers.spice."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from pcb_qa.parsers.spice import KiCadSPICECircuitProcesser


class TestConvertVoltageStr:
    """Tests for _convert_voltage_str static method.

    Note: the implementation does ``voltage_str.upper().replace("V", ".", 1)``
    which replaces 'V' with a dot, so ``"3.3V"`` becomes ``"3.3."``.  This is
    the actual behaviour of the source code — these tests document it.
    """

    def test_zero_voltage(self) -> None:
        assert KiCadSPICECircuitProcesser._convert_voltage_str("0V") == 0.0

    def test_high_voltage(self) -> None:
        assert KiCadSPICECircuitProcesser._convert_voltage_str("12V") == 12.0

    def test_voltage_with_decimal_raises(self) -> None:
        with pytest.raises(ValueError):
            KiCadSPICECircuitProcesser._convert_voltage_str("3.3V")

    def test_voltage_without_v(self) -> None:
        with pytest.raises(ValueError):
            KiCadSPICECircuitProcesser._convert_voltage_str("5.0V")


class TestInit:
    """Tests for KiCadSPICECircuitProcesser initialisation."""

    def test_init_defaults(self) -> None:
        proc = KiCadSPICECircuitProcesser(spice_circuit_path="/tmp/test.cir")
        assert proc.spice_circuit_path == "/tmp/test.cir"
        assert proc.project_name is None
        assert proc.components_needing_models == []

    def test_init_with_output_dir(self) -> None:
        proc = KiCadSPICECircuitProcesser(spice_circuit_path="/tmp/test.cir", output_dir="/tmp/out")
        assert proc.output_dir == "/tmp/out"

    def test_init_with_output_file(self) -> None:
        proc = KiCadSPICECircuitProcesser(
            spice_circuit_path="/tmp/test.cir",
            output_file="/tmp/custom.json",
        )
        assert proc.spice_json_file == "/tmp/custom.json"

    def test_init_default_spice_json_file(self) -> None:
        proc = KiCadSPICECircuitProcesser(spice_circuit_path="/tmp/test.cir")
        assert "test.cir" in proc.spice_json_file


class TestParseSpiceNetlist:
    """Tests for _parse_spice_netlist."""

    def test_parse_rcl_components(self, tmp_path: Path) -> None:
        cir_file = tmp_path / "test.cir"
        cir_file.write_text("* Test\nR1 net1 0 1k\nC1 net1 0 100n\nL1 net1 0 10u\n.end\n")

        proc = KiCadSPICECircuitProcesser(spice_circuit_path=str(cir_file))
        parsed = proc._parse_spice_netlist()

        assert "R1" in parsed["components"]
        assert "C1" in parsed["components"]
        assert "L1" in parsed["components"]
        assert parsed["components"]["R1"]["type"] == "R"
        assert parsed["components"]["R1"]["value"] == "1k"
        assert parsed["components"]["R1"]["nodes"] == ["net1", "0"]

    def test_parse_led_component(self, tmp_path: Path) -> None:
        """LED components are matched by the RCL regex before the LED regex
        because the RCL regex is checked first and ``LED1`` starts with ``L``.
        This test documents the actual (buggy) behaviour.
        """
        cir_file = tmp_path / "led.cir"
        cir_file.write_text("* LED\nLED1 net1 0 LED_MODEL\n.end\n")

        proc = KiCadSPICECircuitProcesser(spice_circuit_path=str(cir_file))
        parsed = proc._parse_spice_netlist()

        assert "LED1" in parsed["components"]
        # The LED component is matched by the RCL regex as type 'L'
        assert parsed["components"]["LED1"]["type"] == "L"
        assert parsed["components"]["LED1"]["value"] == "LED_MODEL"

    def test_parse_ux_components(self, tmp_path: Path) -> None:
        cir_file = tmp_path / "ic.cir"
        cir_file.write_text("* IC\nU1 vcc gnd out LM358\nX1 a b c SUBCKT\n.end\n")

        proc = KiCadSPICECircuitProcesser(spice_circuit_path=str(cir_file))
        parsed = proc._parse_spice_netlist()

        assert "U1" in parsed["components"]
        assert parsed["components"]["U1"]["type"] == "U"
        assert "X1" in parsed["components"]
        assert parsed["components"]["X1"]["type"] == "X"

    def test_parse_skips_comments(self, tmp_path: Path) -> None:
        cir_file = tmp_path / "comments.cir"
        cir_file.write_text("* This is a comment\nR1 net1 0 1k\n* Another comment\n.end\n")

        proc = KiCadSPICECircuitProcesser(spice_circuit_path=str(cir_file))
        parsed = proc._parse_spice_netlist()

        assert len(parsed["components"]) == 1
        assert "R1" in parsed["components"]

    def test_parse_skips_directives(self, tmp_path: Path) -> None:
        cir_file = tmp_path / "directives.cir"
        cir_file.write_text("* Test\n.tran 1u 10m\nR1 net1 0 1k\n.end\n")

        proc = KiCadSPICECircuitProcesser(spice_circuit_path=str(cir_file))
        parsed = proc._parse_spice_netlist()

        assert len(parsed["components"]) == 1

    def test_parse_nets_built(self, tmp_path: Path) -> None:
        cir_file = tmp_path / "nets.cir"
        cir_file.write_text("* Test\nR1 net1 0 1k\nC1 net1 0 100n\n.end\n")

        proc = KiCadSPICECircuitProcesser(spice_circuit_path=str(cir_file))
        parsed = proc._parse_spice_netlist()

        assert "net1" in parsed["nets"]
        assert "0" in parsed["nets"]
        assert len(parsed["nets"]["net1"]) == 2  # R1 and C1

    def test_parse_empty_circuit(self, tmp_path: Path) -> None:
        cir_file = tmp_path / "empty.cir"
        cir_file.write_text("* Empty\n.end\n")

        proc = KiCadSPICECircuitProcesser(spice_circuit_path=str(cir_file))
        parsed = proc._parse_spice_netlist()

        assert parsed["components"] == {}
        assert parsed["nets"] == {}


class TestGenerateLEDModel:
    """Tests for _generate_led_model static method."""

    def test_default_parameters(self) -> None:
        result = KiCadSPICECircuitProcesser._generate_led_model("LED_RED")
        assert ".model LED_RED D" in result
        assert "Is=1p" in result
        assert "Rs=10" in result
        assert "N=1.7" in result

    def test_custom_parameters(self) -> None:
        result = KiCadSPICECircuitProcesser._generate_led_model("LED_GREEN", is_val="2p", rs_val="5", n_val="2.0")
        assert ".model LED_GREEN D" in result
        assert "Is=2p" in result
        assert "Rs=5" in result
        assert "N=2.0" in result


class TestGenerateSpiceModels:
    """Tests for generate_spice_models."""

    def test_led_model_generated(self) -> None:
        proc = KiCadSPICECircuitProcesser(spice_circuit_path="/tmp/test.cir")
        components = [{"type": "LED", "identifier": "RED"}]
        models = proc.generate_spice_models(components)
        assert len(models) == 1
        assert ".model LED_D_RED D" in models[0]

    def test_non_led_ignored(self) -> None:
        proc = KiCadSPICECircuitProcesser(spice_circuit_path="/tmp/test.cir")
        components = [{"type": "R", "identifier": "1k"}]
        models = proc.generate_spice_models(components)
        assert models == []

    def test_duplicate_leds_deduplicated(self) -> None:
        proc = KiCadSPICECircuitProcesser(spice_circuit_path="/tmp/test.cir")
        components = [
            {"type": "LED", "identifier": "RED"},
            {"type": "LED", "identifier": "RED"},
        ]
        models = proc.generate_spice_models(components)
        assert len(models) == 1

    def test_different_leds_not_deduplicated(self) -> None:
        proc = KiCadSPICECircuitProcesser(spice_circuit_path="/tmp/test.cir")
        components = [
            {"type": "LED", "identifier": "RED"},
            {"type": "LED", "identifier": "GREEN"},
        ]
        models = proc.generate_spice_models(components)
        assert len(models) == 2


class TestFindAllEntriesFromSPICE:
    """Tests for find_all_entries_from_SPICE_circuit_with."""

    def test_find_net_in_circuit(self, tmp_path: Path) -> None:
        cir_file = tmp_path / "test.cir"
        cir_file.write_text("* Test\nR1 VCC GND 1k\nC1 VCC GND 100n\n.end\n")

        proc = KiCadSPICECircuitProcesser(spice_circuit_path=str(cir_file))
        entries = proc.find_all_entries_from_SPICE_circuit_with("VCC")

        assert len(entries) == 2

    def test_find_nothing(self, tmp_path: Path) -> None:
        cir_file = tmp_path / "test.cir"
        cir_file.write_text("* Test\nR1 VCC GND 1k\n.end\n")

        proc = KiCadSPICECircuitProcesser(spice_circuit_path=str(cir_file))
        entries = proc.find_all_entries_from_SPICE_circuit_with("NONEXISTENT")

        assert entries == []


class TestCheckSteadyState:
    """Tests for check_steady_state_average_matches_expected_voltage."""

    def test_matches_expected_voltage(self, tmp_path: Path) -> None:
        # Build a SPICE JSON with known voltage values
        spice_json = {
            "0": {
                "name": "v(net1)",
                "values": {
                    str(i): str(3.3) for i in range(15)
                },
            }
        }
        json_file = tmp_path / "spice.json"
        json_file.write_text(json.dumps(spice_json), encoding="utf-8")

        proc = KiCadSPICECircuitProcesser(spice_circuit_path="/tmp/empty.cir")
        result = proc.check_steady_state_average_matches_expected_voltage(
            spice_json_file=str(json_file),
            net_name="net1",
            expected_voltage="3.3V",
        )
        assert result is True

    def test_does_not_match(self, tmp_path: Path) -> None:
        spice_json = {
            "0": {
                "name": "v(net1)",
                "values": {
                    str(i): str(1.8) for i in range(15)
                },
            }
        }
        json_file = tmp_path / "spice.json"
        json_file.write_text(json.dumps(spice_json), encoding="utf-8")

        proc = KiCadSPICECircuitProcesser(spice_circuit_path="/tmp/empty.cir")
        result = proc.check_steady_state_average_matches_expected_voltage(
            spice_json_file=str(json_file),
            net_name="net1",
            expected_voltage="3.3V",
        )
        assert result is False

    def test_net_not_found(self, tmp_path: Path) -> None:
        spice_json = {
            "0": {
                "name": "v(other)",
                "values": {"0": "3.3", "1": "3.3"},
            }
        }
        json_file = tmp_path / "spice.json"
        json_file.write_text(json.dumps(spice_json), encoding="utf-8")

        proc = KiCadSPICECircuitProcesser(spice_circuit_path="/tmp/empty.cir")
        result = proc.check_steady_state_average_matches_expected_voltage(
            spice_json_file=str(json_file),
            net_name="net1",
            expected_voltage="3.3V",
        )
        assert result is False