from enum import Enum, auto
from pydantic import BaseModel, ConfigDict, Field

import circuit_json, kicad_netlist_processer, kicad_spice_circuit_processer, project_files

from circuit_json import CircuitJSON
from kicad_netlist_processer import KiCadNetlistProcesser
from kicad_spice_circuit_processer import KiCadSPICECircuitProcesser 
from project_files import ProjectFiles

class ToolCaller:
    class Mode(Enum):
        JSON_CIRCUIT_AND_SPICE_JSON = 1 # .JSON.net & .JSON.cir
        PRIMITIVE = 2 # .net and .cir
        JSON_CIRCUIT_AND_SPICE_CONTENTS = 3 # .JSON.net & .cir
        SPICE_JSON_AND_NETLIST_CONTENTS = 4 # .JSON.cir & .net
        JSON_NET = 5 # .JSON.net
        JSON_CIRCUIT = 6 # .JSON.cir (not enough information though)
        NET = 7 # .net 
        CIRCUIT = 8 # .cir (not enough information though)
        SCHEMATIC_PDF = 9 # .sch as PDF
        INVALID = auto()

    class QuestionReasoning(BaseModel):
        model_config = ConfigDict(extra='forbid', populate_by_name=True)

        answer: bool = Field(description="The answer to the question (only answer True/False, no explanations)")
        reasoning: str = Field(description="1 sentence reasoning behind the answer")
        is_final: bool = Field(description="Whether this is the final answer or if further tool calls are needed. Be sure in your decision before marking as final.")

    class ToolCalls(BaseModel):
        model_config = ConfigDict(extra='forbid', populate_by_name=True)

        function_name: str = Field(alias="name", description="Name of the function being called")
        function_args: dict = Field(alias="arguments", 
                                    description="Arguments for the function being called",
                                    required=True,
                                    json_schema_extra={"additionalProperties": False})

    def __init__(self):
        self.llm_tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_relevant_context_from_question",
                    "description": "Check component specifications in datasheet and see if they match the question",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "description": "The question to answer"},
                            "project_context": {
                                "type": "object", 
                                "description": "Context of the project, including file paths for circuit JSON, spice JSON, and datasheet files", 
                                "properties": {  
                                    "circuit_json_file": {"type": "string", "description": "Path to circuit JSON"},
                                    "spice_json_file": {"type": "string", "description": "Path to SPICE netlist JSON"},
                                    "datasheet_files": {
                                        "type": "array",
                                        "items": {"type": "string", "description": "Path to datasheet files associated with the project"}
                                    }
                                },
                                "required": ["circuit_json_file", "spice_json_file", "datasheet_files"],  
                                "additionalProperties": False  
                            },
                            "component_ref": {"type": "string", "description": "Reference designator (e.g., R1, U2)"},
                        },
                        "required": ["question", "project_context", "component_ref"],
                        "additionalProperties": False 
                    },
                    "strict": True  
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "calculate_spice_behaviour",
                    "description": "Analyse signal behavior in SPICE simulation and answer the question based on voltage characteristics",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "net_name": {"type": "string", "description": "Net name (e.g. SWDIO, net-_u4-vcomh_, net-_a2-btn_, GND)"},
                            "spice_json_file": {"type": "string", "description": "Path to the SPICE JSON file"},
                            "expected_voltage": {"type": "string", "description": "Expected voltage level (e.g. 3.3V)"}
                        },
                        "required": ["net_name", "spice_circuit_file", "expected_voltage"],
                        "additionalProperties": False  
                    },
                    "strict": True  
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_connections_for_component",
                    "description": "Check if a component is connected to a net in the layout and answer the question based on the connections",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "circuit_json_file": {"type": "string", "description": "Path to the circuit JSON file"},
                            "component_ref": {"type": "string", "description": "Component reference (e.g. C1, U2)"},
                            "net_name": {"type": "string", "description": "Net name (e.g. GND, VCC, SWDIO)"}
                        },
                        "required": ["circuit_json_file", "component_ref", "net_name"],
                        "additionalProperties": False 
                    },
                    "strict": True  
                }
            }
        ]

        self.available_functions = {
            "get_relevant_context_from_question": self.get_relevant_context_from_question,
            "calculate_spice_behaviour": self.calculate_spice_behaviour,
            "find_connections_for_component": self.find_connections_for_component
        }

    def embed_datasheet(datasheet_file: str):
        text = ""
        
        try:
            with pdfplumber.open(datasheet_file) as pdf:
                for page in pdf.pages:
                    text += page.extract_text()
        except FileNotFoundError as e:
            print(e)
            raise e
            
        print(f"Splitting text and creating embeddings for {datasheet_file}...")
        
        # Split text into chunks for better semantic retrieval
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )
        chunks = splitter.split_text(text)
        
        # Load free embedding model
        model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Generate embeddings
        embeddings = model.encode(chunks, convert_to_numpy=True)
        
        # Create FAISS index (Vector Store)
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings)

        chunked_data = []
        for i, chunk in enumerate(chunks):
            chunked_data.append({
                "faiss_index_id": i,                # Explicit ID matching FAISS index
                "text": chunk,                      # The actual content
            })

        target_file_parent = os.path.dirname(os.path.dirname(datasheet_file)) + "/" + "embeddings"

        chunks_store_file_path = target_file_parent + "/" + datasheet_file.split('/')[-1].split('.')[0] + "_chunks.json"
        with open(chunks_store_file_path, "w", encoding="utf-8") as f:
            json.dump(chunked_data, f, ensure_ascii=False, indent=2)
            print(f"✓ Document chunks saved to {chunks_store_file_path}")

        index_file_path = target_file_parent + "/" + datasheet_file.split('/')[-1].split('.')[0] + '_embeddings.index'
        faiss.write_index(index, index_file_path)
        print(f"✓ FAISS index saved to {index_file_path}")

        # return index, chunks, model

    def find_and_embed_datasheets_for_project(self, project_files: dict, project_name: str):
        for datasheet_file in project_files[project_name]["datasheet_files"]:
            embed_datasheet(datasheet_file)

    def get_relevant_context_from_question(self,
                                           question: str,
                                           project_context: dict,
                                           component_ref: str) -> list:

        try:
            print("Project context:", project_context)
            parent_directory = os.path.dirname(project_context["circuit_json_file"])

            component_prefix_file_path = f"{parent_directory}/embeddings/{component_ref}"
            loaded_index = faiss.read_index(f"{component_prefix_file_path}_embeddings.index")

            with open(f"{component_prefix_file_path}_chunks.json", "r", encoding="utf-8") as f:
                stored_data = json.load(f)

            model = SentenceTransformer("all-MiniLM-L6-v2")
            query_embedding = model.encode([question], convert_to_numpy=True)

            # Search for the top 3 nearest neighbors
            distances, indices = loaded_index.search(query_embedding, 3)

            relevant_context = []

            for i, idx in enumerate(indices[0]):
                item = stored_data[idx] 
                relevant_context.append(item["text"])

            return relevant_context
        except Exception as e:
            print(f"Error retrieving context for datasheets in {project_context["datasheet_files"]}:", e)
            return []

    def calculate_spice_behaviour(self, 
                                  spice_json_file: str, 
                                  net_name: str, 
                                  expected_voltage: str):
        try: 
            spice_circuit_processer = KiCadSPICECircuitProcesser(spice_circuit_path="", project_name=None, output_file=spice_json_file)
            return spice_circuit_processer.check_steady_state_average_matches_expected_voltage(spice_json_file=spice_json_file, net_name=net_name, expected_voltage=expected_voltage)
        
        except Exception as e:
            print("Error in calculating SPICE behaviour:", e)
            return False

    def find_connections_for_component(self, 
                                       circuit_json_file: str, 
                                       component_ref: str, 
                                       net_name: str) -> bool:

        try:
            circuit_json_object = CircuitJSON(circuit_file=circuit_json_file)
            return circuit_json_object.is_component_in_net_from_circuit(component_ref, net_name)
        except Exception as e:
            print("Error in finding connections for component:", e)
            return False

    def find_all_entries_from_netlist_file_with(self, project_context: dict, component_ref: str) -> str:
        netlist_processer = KiCadNetlistProcesser(netlist_path=project_context["netlist_file"], output_dir=project_context["parent_directory"]+"/dry_run")
        return netlist_processer.find_all_entries_from_netlist_file_with(component_ref).to_str()

    def find_all_entries_from_SPICE_circuit_with(self, project_context: dict, net_name: str):
        spice_circuit_processer = KiCadSPICECircuitProcesser(spice_circuit_path=project_context["spice_circuit_file"], project_name=None, output_file=project_context["spice_json_file"])
        spice_circuit_processer.find_all_entries_from_SPICE_circuit_with(net_name)

if __name__ == "__main__":
    tool_caller = ToolCaller()
    acorn_robot_project = vars(ProjectFiles().initialise_acorn_robot_project())
    # print(acorn_robot_project)
    tool_caller.find_all_entries_from_SPICE_circuit_with(acorn_robot_project, "SERIAL_CAN_PWR_3.3V")

    # ans = tool_caller.calculate_spice_behaviour(spice_json_file=acorn_robot_project["spice_json_file"], net_name="ser_select", expected_voltage="0.0V")
    # print(ans)

    # # Returns True
    # ans = tool_caller.calculate_spice_behaviour(spice_json_file=acorn_robot_project["spice_json_file"], net_name="ser_select", expected_voltage="3.3V")
    # print(ans)

    # # Returns True
    # ans = tool_caller.find_connections_for_component(circuit_json_file=acorn_robot_project["circuit_json_file"], component_ref="C18", net_name="GND")
    # print(ans)

    # ans = tool_caller.find_connections_for_component(circuit_json_file=acorn_robot_project["circuit_json_file"], component_ref="C18", net_name="FB")
    # print(ans)