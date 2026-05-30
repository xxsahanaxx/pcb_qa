"""LLM tool-calling interface for PCB circuit analysis.

Refactored from the original ``tool_caller.py``.
"""

from __future__ import annotations

import json
import os
from typing import Any

from pcb_qa.logging_config import logger
from pcb_qa.models.project import Project, ProjectFiles
from pcb_qa.models.tool_definitions import ToolDefinitions
from pcb_qa.parsers.circuit_json import CircuitJSON
from pcb_qa.parsers.netlist import KiCadNetlistProcesser
from pcb_qa.parsers.spice import KiCadSPICECircuitProcesser


class ToolCaller:
    """Expose circuit-analysis functions as callable tools for the LLM.

    The three primary tools are:

    * ``get_relevant_context_from_question`` — semantic search over datasheets.
    * ``calculate_spice_behaviour`` — check steady-state voltages.
    * ``find_connections_for_component`` — check component-to-net connectivity.
    """

    def __init__(self) -> None:
        self.llm_tools = ToolDefinitions.all_tools()
        self.available_functions: dict[str, Any] = {
            "get_relevant_context_from_question": self.get_relevant_context_from_question,
            "calculate_spice_behaviour": self.calculate_spice_behaviour,
            "find_connections_for_component": self.find_connections_for_component,
        }

    # -- datasheet embedding --------------------------------------------------

    @staticmethod
    def embed_datasheet(datasheet_file: str) -> None:
        """Create FAISS embeddings for a datasheet PDF."""
        import faiss
        import pdfplumber
        from sentence_transformers import SentenceTransformer
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        text = ""
        try:
            with pdfplumber.open(datasheet_file) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
        except FileNotFoundError:
            logger.error("Datasheet not found: %s", datasheet_file)
            raise

        logger.info("Embedding datasheet: %s", datasheet_file)
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_text(text)

        model = SentenceTransformer("all-MiniLM-L6-v2")
        embeddings = model.encode(chunks, convert_to_numpy=True)

        index = faiss.IndexFlatL2(embeddings.shape[1])
        index.add(embeddings)

        chunked_data = [{"faiss_index_id": i, "text": chunk} for i, chunk in enumerate(chunks)]

        target_dir = os.path.join(os.path.dirname(os.path.dirname(datasheet_file)), "embeddings")
        os.makedirs(target_dir, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(datasheet_file))[0]
        chunks_path = os.path.join(target_dir, f"{base_name}_chunks.json")
        index_path = os.path.join(target_dir, f"{base_name}_embeddings.index")

        with open(chunks_path, "w", encoding="utf-8") as fh:
            json.dump(chunked_data, fh, ensure_ascii=False, indent=2)
        faiss.write_index(index, index_path)
        logger.info("Saved embeddings for %s", datasheet_file)

    def find_and_embed_datasheets_for_project(self, project: Project) -> None:
        for ds in project.datasheet_files:
            self.embed_datasheet(ds)

    # -- tool implementations -------------------------------------------------

    def get_relevant_context_from_question(
        self,
        question: str,
        project_context: dict[str, Any],
        component_ref: str,
    ) -> list[str]:
        """Semantic search over embedded datasheets for relevant context."""
        import faiss
        from sentence_transformers import SentenceTransformer

        try:
            parent_dir = os.path.dirname(project_context["circuit_json_file"])
            prefix = os.path.join(parent_dir, "embeddings", component_ref)

            index = faiss.read_index(f"{prefix}_embeddings.index")
            with open(f"{prefix}_chunks.json", "r", encoding="utf-8") as fh:
                stored_data = json.load(fh)

            model = SentenceTransformer("all-MiniLM-L6-v2")
            query_embedding = model.encode([question], convert_to_numpy=True)
            _, indices = index.search(query_embedding, 3)

            return [stored_data[idx]["text"] for idx in indices[0]]
        except Exception as exc:
            logger.error("Error retrieving context for %s: %s", project_context.get("datasheet_files"), exc)
            return []

    def calculate_spice_behaviour(
        self,
        spice_json_file: str,
        net_name: str,
        expected_voltage: str,
    ) -> bool:
        try:
            processer = KiCadSPICECircuitProcesser(spice_circuit_path="", output_file=spice_json_file)
            return processer.check_steady_state_average_matches_expected_voltage(
                spice_json_file=spice_json_file, net_name=net_name, expected_voltage=expected_voltage,
            )
        except Exception as exc:
            logger.error("Error calculating SPICE behaviour: %s", exc)
            return False

    def find_connections_for_component(
        self,
        circuit_json_file: str,
        component_ref: str,
        net_name: str,
    ) -> bool:
        try:
            circuit = CircuitJSON(circuit_file=circuit_json_file)
            return circuit.is_component_in_net_from_circuit(component_ref, net_name)
        except Exception as exc:
            logger.error("Error finding connections: %s", exc)
            return False

    def find_all_entries_from_netlist_file_with(
        self,
        project_context: dict[str, Any],
        component_ref: str,
    ) -> str:
        processer = KiCadNetlistProcesser(
            netlist_path=project_context["netlist_file"],
            output_dir=os.path.join(project_context["parent_directory"], "dry_run"),
        )
        return processer.find_all_entries_from_netlist_file_with(component_ref).to_str()

    def find_all_entries_from_SPICE_circuit_with(
        self,
        project_context: dict[str, Any],
        net_name: str,
    ) -> list[str]:
        processer = KiCadSPICECircuitProcesser(
            spice_circuit_path=project_context["spice_circuit_file"],
            output_file=project_context["spice_json_file"],
        )
        return processer.find_all_entries_from_SPICE_circuit_with(net_name)