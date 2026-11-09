"""Ask an LLM whether a netlist (optionally + SPICE circuit) deviates from a
hardware design-specification document, i.e. whether it contains an anomaly
(hardware trojan or otherwise).

Uses this repo's existing OpenRouter-backed OpenAI-compatible client
(``pcb_qa.config.get_openai_client``, same ``OPENROUTER_API_KEY`` /
``OPENROUTER_BASE_URL`` env vars as the rest of the benchmark pipeline), so
``model`` is an OpenRouter model slug (e.g. ``"gpt-5.4-nano"``,
``"claude-sonnet-4.6"``), not a raw OpenAI one.

Usage::

    python netlist_modifications/scripts/detect_anomaly_with_design_spec.py \\
        --design-doc docs/design_specs/acorn-robot-electronics.md \\
        --netlist outputs/Infected/ComponentSubstitution/Tolerance/AcornRobotElectronics/C3/cm4-robot.net \\
        --spice outputs/Infected/ComponentSubstitution/Tolerance/AcornRobotElectronics/C3/cm4_robot_board.cir \\
        --model gpt-5.4-nano \\
        --output /tmp/c3_anomaly_check.json

Run against the Clean netlist for the same project to sanity-check that the
same prompt does *not* flag an anomaly when none exists (no false positive
on the un-infected board).
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow running from the repo root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from pcb_qa.config import get_openai_client
from pcb_qa.models.tool_definitions import QuestionReasoning
from pcb_qa.utils.file_ops import save_debug_json

DEFAULT_MODEL = "gpt-5.4-nano"
DEFAULT_TEMPERATURE = 0.0


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def detect_anomaly(
    design_doc_path: str,
    netlist_path: str,
    spice_path: str | None = None,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Ask *model* whether the netlist (and optional SPICE circuit) at the
    given paths deviates from the design-specification document.

    Parameters
    ----------
    design_doc_path:
        Path to a Markdown design-specification document (e.g. one of the
        files under ``docs/design_specs/``).
    netlist_path:
        Path to a KiCad S-expression netlist (``.net``) — clean or infected.
    spice_path:
        Optional path to the matching SPICE circuit (``.cir``). Omit to run
        a netlist-only check.
    model:
        OpenRouter model slug to query.

    Returns
    -------
    dict
        ``{"answer": "YES"|"NO", "reasoning": str, "is_final": bool,
        "raw_response": dict}``. ``answer`` is ``"YES"`` if the model
        believes an anomaly is present.
    """
    design_doc = _read_text(design_doc_path)
    netlist_contents = _read_text(netlist_path)
    spice_contents = _read_text(spice_path) if spice_path else None

    client = get_openai_client()

    prompt = (
        "You are a Hardware Security and Design Review Expert. You are given "
        "a human/LLM-written design-specification document for a PCB project, "
        "and the actual KiCad netlist for that same board (optionally with its "
        "SPICE circuit representation).\n\n"
        "Your task: decide whether the netlist contains an ANOMALY — a "
        "hardware trojan, a malicious component substitution, a severed/"
        "rerouted trace, or any other deviation from sound design — and "
        "explain exactly what it is if so.\n\n"
        "Important grounding rules:\n"
        "- The design doc is a narrative summary. It only describes "
        "components/nets that had a stated rationale in the project's own "
        "notes/TODOs — it does NOT enumerate every net or component. The doc "
        "being silent about a component is NOT evidence of an anomaly.\n"
        "- Only report an anomaly if you find concrete evidence in the "
        "netlist itself: e.g. a component's own declared description/"
        "datasheet text contradicting one of its properties (such as a "
        "'Tolerance' property that disagrees with a vendor-stated '±X%' in "
        "the same component's description), an implausible component value "
        "for its role, or a net that has been split/renamed/rerouted in a "
        "way inconsistent with a sane PCB design.\n"
        "- Do not hallucinate an anomaly to satisfy the question. If nothing "
        "looks wrong, say so.\n\n"
        "DESIGN SPECIFICATION DOCUMENT:\n"
        "----------------------------------------\n"
        f"{design_doc}\n\n"
        "NETLIST:\n"
        "----------------------------------------\n"
        f"{netlist_contents}\n\n"
    )

    if spice_contents is not None:
        prompt += (
            "SPICE CIRCUIT:\n"
            "----------------------------------------\n"
            f"{spice_contents}\n\n"
        )

    prompt += (
        "Answer the question in the specified format requested by the user.\n"
        "Once you are completely sure with your answer, set the 'is_final' "
        "attribute to True in your output response.\n"
        "Make sure you explain your reasoning clearly in the 'reasoning' "
        "attribute of the output response, citing the specific "
        "component/net/property that makes it an anomaly (or, if none, why "
        "nothing qualifies)."
    )

    question = (
        "Does this netlist contain an anomaly (hardware trojan or other "
        "malicious/erroneous deviation) relative to sound design practice? "
        "If yes, name the exact component/net and property involved."
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": question},
    ]

    llm_response = client.responses.parse(
        model=model,
        input=messages,
        text_format=QuestionReasoning,
        temperature=DEFAULT_TEMPERATURE,
    )

    raw = llm_response.model_dump()
    parsed = llm_response.output[0].content[0].parsed.model_dump()
    parsed["answer"] = "YES" if parsed["answer"] is True else "NO"
    parsed["raw_response"] = raw
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design-doc", required=True, help="Path to the design-spec Markdown file")
    parser.add_argument("--netlist", required=True, help="Path to the KiCad .net file")
    parser.add_argument("--spice", default=None, help="Optional path to the matching .cir SPICE file")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"OpenRouter model slug (default: {DEFAULT_MODEL})")
    parser.add_argument("--output", default=None, help="Optional path to save the full JSON result")
    args = parser.parse_args()

    result = detect_anomaly(
        design_doc_path=args.design_doc,
        netlist_path=args.netlist,
        spice_path=args.spice,
        model=args.model,
    )

    print(f"Anomaly detected: {result['answer']}")
    print(f"Reasoning: {result['reasoning']}")

    if args.output:
        save_debug_json(args.output, result)
        print(f"\nFull result saved to {args.output}")


if __name__ == "__main__":
    main()
