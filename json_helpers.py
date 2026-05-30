import json

class JSONFileOperator: 
    def __init__(self):
        pass

    def read_from_json_file(self, read_file: str) -> dict:
        with open(read_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def write_to_json_file(self, contents: dict, output_file: str):
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(contents, f, indent=4, ensure_ascii=False)
